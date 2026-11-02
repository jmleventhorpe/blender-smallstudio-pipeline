"""Starting, saving and opening workfiles in Blender. The rules are in core.workfiles."""

from __future__ import annotations

from pathlib import Path

import bpy

from ..core.config import Config
from ..core.entities import Asset, Entity
from ..core.errors import PipelineError
from ..core.workfiles import new_workfile
from .identity import asset_identity, create_root_collection


def start_workfile(entity: Entity, task: str) -> Path:
    """Start a task's first workfile from its starter (or an empty file) and save it as v001."""
    plan = new_workfile(entity, task)  # Raises before anything in Blender changes.
    if plan.starter is not None:
        bpy.ops.wm.open_mainfile(filepath=str(plan.starter), load_ui=False)
    else:
        bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    apply_project_settings(scene, entity.project.config)
    if isinstance(entity, Asset) and not any(map(asset_identity, bpy.data.collections)):
        create_root_collection(entity, scene)
    plan.path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(plan.path))
    return plan.path


def apply_project_settings(scene: bpy.types.Scene, config: Config) -> None:
    scene.render.fps = config.fps
    scene.render.fps_base = 1.0
    scene.render.resolution_x, scene.render.resolution_y = config.resolution
    scene.render.resolution_percentage = 100


def has_unsaved_changes() -> bool:
    """Whether the open file has changes since it was saved. (A function so tests can
    stand in for it: Python edits don't set the flag in background mode.)"""
    return bpy.data.is_dirty


def save_changes() -> None:
    """Save the open file where it is."""
    if not bpy.data.filepath:
        raise PipelineError("This file has never been saved. Save it first, or choose Don't Save.")
    bpy.ops.wm.save_mainfile()
