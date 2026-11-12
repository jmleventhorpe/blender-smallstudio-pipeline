"""Keeping things in step with the open file, through Blender's load and save handlers.

After a file loads: refresh the state, mark the file as in use (or warn whose it is),
register the project's asset library, note the versions of the publishes it links, and
show its cut, if it has one. Before a save, new instances get their IDs and a cut's
playblast output follows the version. After a save, including Save As and Version Up,
the in-use marker moves to the new file. A lighting file's render paths follow the
workfile's version, and a comp scene reads its shot's renders before it renders.
Warnings pop up once the UI is ready; the Pipeline tab redraws when the selection, the
clicked collection or the scene on show changes (note_picks).
"""

from __future__ import annotations

import atexit
import contextlib
from pathlib import Path
from typing import Any

import bpy
from bpy.app.handlers import persistent

from ..common.errors import PipelineError
from ..interface.panels import redraw_sidebars
from ..lighting.blender import renders
from ..loading.blender import instances, libraries, updates
from ..project.blender import nodes
from ..project.blender.nodes import LIGHT
from ..publishing.blender import results, review
from ..shots.blender import layout
from ..workfiles.core import inuse
from ..workfiles.core.context import file_context
from . import state

# The workfile whose in-use marker this Blender holds.
_claimed: Path | None = None


@persistent
def on_load_pre(*_args: object) -> None:
    """Before another file opens: give up this one's in-use marker."""
    release()


@persistent
def on_load_post(*_args: object) -> None:
    """After a file opens: work out what it is, mark it in use, and warn if need be."""
    results.clear()  # They were for the file just closed.
    review.clear()
    nodes.picked = "collection"
    _seen_picks.clear()
    state.refresh()
    claim()
    after_open()
    show_cut()
    if state.current.warnings and state.current.context is not None:
        show_message(*state.current.warnings)  # Publishes, files in use.


def after_open() -> None:
    """Library bookkeeping for the open file's project."""
    project = state.current.project
    if project is None:
        return
    if libraries.register_asset_library(project):
        show_message(f"Added {project.root.name}'s assets to the Asset Browser.", icon="INFO")
    updates.remember_versions(project)


def show_cut() -> None:
    """In a file holding a sequence's node, show its cut in the sequencer, with a marker
    per shot."""
    project = state.current.project
    if project is None or not layout.has_cut():
        return
    with contextlib.suppress(PipelineError):  # A sequence that isn't in this project.
        master = layout.master_scene()
        layout.show_cut_in_sequencer(master)
        sequence_node = nodes.sequence_node(master)
        assert sequence_node is not None  # master_scene holds it.
        layout.sync_markers(master, project.sequence(sequence_node.name))
    file = state.current.context
    if file is not None and file.version and layout.cut_task() == LIGHT:
        renders.set_render_paths(project, file.version)  # Renders made since show in comp.


@persistent
def on_save_pre(path: object = "", *_args: object) -> None:
    """Before a save (or a publish's copy, spike T13): number new instances in every scene,
    and point a cut's playblast output at the version being saved and its markers at the cut."""
    for scene in bpy.data.scenes:
        instances.number_instances(scene)
    project = state.current.project
    if project is None or not isinstance(path, str) or not path:
        return
    file = file_context(project, Path(path))  # Save As and Version Up save somewhere new.
    if file and file.version and layout.cut_task() == LIGHT:
        renders.set_render_paths(project, file.version)
    if file and file.version and layout.cut_task() == layout.LAYOUT:
        try:
            master = layout.master_scene()
        except PipelineError:
            return
        sequence = project.sequence(file.entity)
        layout.set_playblast_output(master, sequence, file.version)
        layout.sync_markers(master, sequence)  # Strips moved by hand since.


@persistent
def on_render_pre(scene: object = None, *_args: object) -> None:
    """Before a comp scene renders: read its shot's lighting renders, made since saving."""
    project, file = state.current.project, state.current.context
    if not isinstance(scene, bpy.types.Scene) or project is None or not file or not file.version:
        return
    code = scene.name.removesuffix(".comp")
    lit = renders.lit_scenes().get(code)
    if code != scene.name and lit is not None:
        renders.connect_renders(scene, lit, renders.render_prefix(project, code, file.version))


@persistent
def on_save_post(*_args: object) -> None:
    """After a save: refresh the state, moving the in-use marker if the file moved."""
    # Save As (and Version Up) moves us to another file: move the marker with it.
    if _claimed != Path(bpy.data.filepath):
        release()
    state.refresh()
    claim()


def claim() -> None:
    """Mark the open workfile as ours, or note who else has it open."""
    global _claimed
    context = state.current.context
    if context is None or context.is_publish or _claimed is not None:
        return
    path = Path(bpy.data.filepath)
    other = inuse.claim(path)
    if other is None:
        _claimed = path
        return
    since = other.opened.astimezone().strftime("%H:%M on %d %b")
    state.current.warnings.append(
        f"{other.user} has this file open on {other.machine} (since {since})."
    )


def release() -> None:
    """Remove the in-use marker this Blender holds, if any."""
    global _claimed
    if _claimed is not None:
        inuse.release(_claimed)
        _claimed = None


def show_message(*lines: str, icon: str = "ERROR") -> None:
    """Pop up a message once the UI is ready. Handlers can't report to the artist directly."""
    if bpy.app.background:
        return

    def popup() -> None:
        def draw(menu: bpy.types.UIPopupMenu, _context: bpy.types.Context) -> None:
            for line in lines:
                menu.layout.label(text=line)

        bpy.context.window_manager.popup_menu(draw, title="Pipeline", icon=icon)  # pyright: ignore[reportArgumentType]

    bpy.app.timers.register(popup, first_interval=0.1)


@persistent
def on_depsgraph_update(*_args: object) -> None:
    """After a change (selecting included): note what's picked, and redraw the Pipeline
    tab if it changed."""
    note_picks()


HANDLERS = (
    (bpy.app.handlers.load_pre, on_load_pre),
    (bpy.app.handlers.load_post, on_load_post),
    (bpy.app.handlers.save_pre, on_save_pre),
    (bpy.app.handlers.save_post, on_save_post),
    (bpy.app.handlers.render_pre, on_render_pre),
    (bpy.app.handlers.depsgraph_update_post, on_depsgraph_update),
)
# Changes that don't update the depsgraph, but change what's picked: the scene on show
# (Follow the cut switches it) and the collection clicked in the Outliner.
# The stubs only allow a struct here; Blender also takes (type, "property") keys.
WATCHED: tuple[Any, ...] = (
    (bpy.types.Window, "scene"),
    (bpy.types.ViewLayer, "active_layer_collection"),
)
_OWNER = object()  # Who the message bus subscriptions belong to.
# What was picked when last noted: per window, the scene, the clicked collection and the
# selection.
_seen_picks: dict[int, tuple[str, str, frozenset[str]]] = {}


def note_picks() -> None:
    """Note whether the clicked collection or the selection changed last (nodes.picked),
    and redraw the Pipeline tab if either did, or the scene on show."""
    window_manager = bpy.context.window_manager
    changed = False
    for window in window_manager.windows if window_manager else ():
        view_layer = window.view_layer
        active = view_layer.active_layer_collection
        now = (
            window.scene.name,
            active.collection.name if active else "",
            frozenset(obj.name for obj in view_layer.objects.selected),
        )
        before = _seen_picks.get(window.as_pointer())
        if before != now:
            changed = True
            if before is not None and before[0] == now[0] and before[1] != now[1]:
                nodes.picked = "collection"
            elif before is not None and before[0] == now[0] and before[2] != now[2]:
                nodes.picked = "selection"
        _seen_picks[window.as_pointer()] = now
    if changed:
        redraw_sidebars()


def register() -> None:
    for handlers, function in HANDLERS:
        handlers.append(function)
    for watched in WATCHED:
        bpy.msgbus.subscribe_rna(
            key=watched, owner=_OWNER, args=(), notify=note_picks, options={"PERSISTENT"}
        )
    atexit.register(release)  # Quitting Blender.


def unregister() -> None:
    release()
    atexit.unregister(release)
    bpy.msgbus.clear_by_owner(_OWNER)
    for handlers, function in HANDLERS:
        if function in handlers:
            handlers.remove(function)
