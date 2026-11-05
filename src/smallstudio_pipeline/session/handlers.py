"""Keeping things in step with the open file, through Blender's load and save handlers.

After a file loads: refresh the state, mark the file as in use (or warn whose it is),
register the project's asset library, note the versions of the publishes it links, and
flag anything built from an older publish. Before a save, new instances in shots get
their IDs and a layout file's playblast output follows its version. After a save,
including Save As and Version Up, the in-use marker moves to the new file. Warnings pop
up once the UI is ready.
"""

from __future__ import annotations

import atexit
import contextlib
from pathlib import Path

import bpy
from bpy.app.handlers import persistent

from ..common.errors import PipelineError
from ..loading.blender import instances, libraries, updates
from ..publishing.blender import results
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
    state.refresh()
    claim()
    after_open()
    show_cut_in_sequencer()
    if state.current.warnings and state.current.context is not None:
        show_message(*state.current.warnings)  # Publishes, files in use, stale builds.


def after_open() -> None:
    """Library bookkeeping for the open file's project."""
    project = state.current.project
    if project is None:
        return
    if libraries.register_asset_library(project):
        show_message(f"Added {project.root.name}'s assets to the Asset Browser.", icon="INFO")
    updates.remember_versions(project)
    stale = updates.stale_builds(project, bpy.context.scene)
    if stale:
        state.current.warnings.append(updates.stale_warning(stale))


def show_cut_in_sequencer() -> None:
    """In a layout workfile, point any workspace's sequencer that edits nothing at the cut."""
    file = state.current.context
    if file is None or file.task != layout.LAYOUT or file.entity_kind != "sequence":
        return
    with contextlib.suppress(PipelineError):  # No master scene: nothing to show.
        layout.show_cut_in_sequencer(layout.master_scene())


@persistent
def on_save_pre(path: object = "", *_args: object) -> None:
    """Before a save (or a publish's copy, spike T13): number new instances in each shot,
    and point a layout workfile's playblast output at the version being saved."""
    for scene in bpy.data.scenes:
        if layout.SHOT in scene:
            instances.number_instances(scene)
    project = state.current.project
    if project is None or not isinstance(path, str) or not path:
        return
    file = file_context(project, Path(path))  # Save As and Version Up save somewhere new.
    if file and file.task == layout.LAYOUT and file.entity_kind == "sequence" and file.version:
        try:
            master = layout.master_scene()
        except PipelineError:
            return
        layout.set_playblast_output(master, project.sequence(file.entity), file.version)


@persistent
def on_save_post(*_args: object) -> None:
    # Save As (and Version Up) moves us to another file: move the marker with it.
    """After a save: refresh the state, moving the in-use marker if the file moved."""
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


HANDLERS = (
    (bpy.app.handlers.load_pre, on_load_pre),
    (bpy.app.handlers.load_post, on_load_post),
    (bpy.app.handlers.save_pre, on_save_pre),
    (bpy.app.handlers.save_post, on_save_post),
)


def register() -> None:
    for handlers, function in HANDLERS:
        handlers.append(function)
    atexit.register(release)  # Quitting Blender.


def unregister() -> None:
    release()
    atexit.unregister(release)
    for handlers, function in HANDLERS:
        if function in handlers:
            handlers.remove(function)
