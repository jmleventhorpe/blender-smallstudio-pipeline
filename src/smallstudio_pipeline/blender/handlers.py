"""Keeping the state, the in-use marker and warnings in step with the open file."""

from __future__ import annotations

import atexit
from pathlib import Path

import bpy
from bpy.app.handlers import persistent

from ..core import inuse
from . import libraries, results, state

# The workfile whose in-use marker this Blender holds.
_claimed: Path | None = None


@persistent
def on_load_pre(*_args: object) -> None:
    release()


@persistent
def on_load_post(*_args: object) -> None:
    results.clear()  # They were for the file just closed.
    state.refresh()
    claim()
    after_open()
    if state.current.warning and state.current.context is not None:
        show_message(state.current.warning)  # Publishes, files in use, stale builds.


def after_open() -> None:
    """Library bookkeeping for the open file's project."""
    project = state.current.project
    if project is None:
        return
    if libraries.register_asset_library(project):
        show_message(f"Added {project.root.name}'s assets to the Asset Browser.", icon="INFO")
    libraries.remember_versions(project)
    stale = libraries.stale_builds(project, bpy.context.scene)
    if stale and state.current.warning is None:
        newer = ", ".join(change.label for change in stale)
        state.current.warning = (
            f"Built from an older publish ({newer}). Carry changes over by hand."
        )


@persistent
def on_save_post(*_args: object) -> None:
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
    state.current.warning = f"{other.user} has this file open on {other.machine} (since {since})."


def release() -> None:
    global _claimed
    if _claimed is not None:
        inuse.release(_claimed)
        _claimed = None


def show_message(message: str, icon: str = "ERROR") -> None:
    """Pop up a message once the UI is ready. Handlers can't report to the artist directly."""
    if bpy.app.background:
        return

    def popup() -> None:
        def draw(menu: bpy.types.UIPopupMenu, _context: bpy.types.Context) -> None:
            menu.layout.label(text=message)

        bpy.context.window_manager.popup_menu(draw, title="Pipeline", icon=icon)  # pyright: ignore[reportArgumentType]

    bpy.app.timers.register(popup, first_interval=0.1)


HANDLERS = (
    (bpy.app.handlers.load_pre, on_load_pre),
    (bpy.app.handlers.load_post, on_load_post),
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
