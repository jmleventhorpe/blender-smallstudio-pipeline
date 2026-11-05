"""Starting, saving and opening workfiles: the Blender side of workfiles/core/workfiles.py.

start_workfile() opens a task's starter file (or an empty one), brings in the publish
the task builds on or creates the asset's root collection, applies the project's frame
rate and resolution, and saves v001. Operators check for unsaved changes through
has_unsaved_changes(), so tests can stand in for Blender's flag.
"""

from __future__ import annotations

from pathlib import Path

import bpy

from ...common.errors import PipelineError
from ...loading.blender import libraries
from ...project.blender.identity import asset_identity, create_root_collection, mark_built_from
from ...project.core.config import Config
from ...project.core.entities import Asset, Entity, Sequence
from ...publishing.core.publishing import Dependency
from ...shots.blender import layout
from ..core.workfiles import new_workfile


def start_workfile(entity: Entity, task: str) -> Path:
    """Start a task's first workfile from its starter (or an empty file) and save it as v001."""
    plan = new_workfile(entity, task)  # Raises before anything in Blender changes.
    if plan.starter is not None:
        bpy.ops.wm.open_mainfile(filepath=str(plan.starter), load_ui=False)
    else:
        bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    apply_project_settings(scene, entity.project.config)
    if isinstance(entity, Asset) and plan.built_from is not None:
        bring_in_root(entity, plan.built_from, scene)
    elif isinstance(entity, Asset) and not any(map(asset_identity, bpy.data.collections)):
        create_root_collection(entity, scene)
    elif isinstance(entity, Sequence) and task == layout.LAYOUT:
        layout.start_cut(scene, entity)
    plan.path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(plan.path))
    return plan.path


def bring_in_root(asset: Asset, publish: Dependency, scene: bpy.types.Scene) -> None:
    """Append an asset's root collection from one of its publishes, e.g. the model for a rig."""
    path = asset.project.root / publish.path
    # clear_asset_data: the hero is marked as an asset, but this workfile's copy mustn't be.
    root = libraries.load_root(path, asset.name, link=False, clear_asset_data=True)
    scene.collection.children.link(root)
    mark_built_from(root, publish)


def apply_project_settings(scene: bpy.types.Scene, config: Config) -> None:
    """Set the scene's frame rate and resolution from the project."""
    scene.render.fps = config.fps
    scene.render.fps_base = 1.0
    scene.render.resolution_x, scene.render.resolution_y = config.resolution
    scene.render.resolution_percentage = 100


def has_unsaved_changes() -> bool:
    """Whether the open file has changes since it was saved.

    A function so tests can stand in for it: Python edits don't set the flag in background
    mode.
    """
    return bpy.data.is_dirty


def save_changes() -> None:
    """Save the open file where it is."""
    if not bpy.data.filepath:
        raise PipelineError("This file has never been saved. Save it first, or choose Don't Save.")
    bpy.ops.wm.save_mainfile()
