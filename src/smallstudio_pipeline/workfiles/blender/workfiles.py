"""Saving workfiles in the right place: the Blender side of workfiles/core/workfiles.py.

new_workfile() saves a new, empty file as an entity's task's next workfile; save_to()
saves the open file there instead. Neither adds anything to the file: nodes say what a
file is working on, and New Node makes them. Operators check for unsaved changes through
has_unsaved_changes(), so tests can stand in for Blender's flag.
"""

from __future__ import annotations

from pathlib import Path

import bpy

from ...common.errors import PipelineError
from ...project.core.entities import Entity
from ..core.workfiles import next_workfile_path


def new_workfile(entity: Entity, task: str) -> Path:
    """Start an empty file and save it as the task's next workfile."""
    path = next_workfile_path(entity, task)  # Raises before anything in Blender changes.
    bpy.ops.wm.read_homefile(use_empty=True)
    return save_as(path)


def save_to(entity: Entity, task: str) -> Path:
    """Save the open file as the task's next workfile."""
    return save_as(next_workfile_path(entity, task))


def save_as(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    return path


def has_unsaved_changes() -> bool:
    """Whether the open file has changes since it was saved.

    A function so tests can stand in for it: Python edits don't set the flag in background
    mode.
    """
    return bpy.data.is_dirty


def save_changes() -> None:
    """Save the open file where it is."""
    if not bpy.data.filepath:
        raise PipelineError(
            "This file has never been saved. Use Save To to save it in the project."
        )
    bpy.ops.wm.save_mainfile()
