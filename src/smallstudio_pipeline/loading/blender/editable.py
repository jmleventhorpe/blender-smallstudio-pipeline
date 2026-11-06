"""Make Editable: swap a linked asset for a local copy to edit inside another asset's file.

make_editable() appends the asset's latest versioned publish where the linked one was,
bakes the placing empty's transform into the copy and keeps it on the copy's root
(PLACEMENT), so publishing can move the copy back into the asset's own space and link the
asset in again where it stood (publishing/blender/in_context.py). Tested as spike T12.
"""

from __future__ import annotations

import bpy
from mathutils import Matrix

from ...common.errors import PipelineError
from ...project.blender.identity import TASK, asset_identity, linked_asset
from ...project.core.project import Project
from . import libraries

# Where the linked asset was placed, kept on the copy's root while it's being edited.
PLACEMENT = "pipeline_placement"  # The placing empty's world matrix, 16 numbers by row.
PLACEMENT_NAME = "pipeline_placement_name"  # The empty's name, to place the link again.


def make_editable(
    empty: bpy.types.Object, project: Project, view_layer: bpy.types.ViewLayer
) -> bpy.types.Collection:
    """Swap the linked asset an empty instances for a local copy, in the same place."""
    linked = linked_asset(empty)
    identity = asset_identity(linked) if linked else None
    if identity is None:
        raise PipelineError("Select the empty that places a linked asset.")
    asset = project.asset(identity[0])
    task = asset.tasks[0]  # Editing in place is that first task's work.
    version = asset.latest_publish_version(task)
    if version is None:
        raise PipelineError(f"{asset.name} has no {task} publish to edit.")
    # The versioned copy, not the hero: this file links the hero, and Blender won't
    # append cleanly from a file it already links.
    source = asset.publish_path(task, version)
    root = libraries.load_root(source, asset.name, link=False)
    root[TASK] = root.get(TASK) or task  # A node for the task it was published as.
    for collection in empty.users_collection:
        collection.children.link(root)

    placement = empty.matrix_world.copy()
    for obj in top_objects(root):
        obj.matrix_basis = placement @ world_matrix(obj, view_layer)
    root[PLACEMENT] = [value for row in placement for value in row]
    root[PLACEMENT_NAME] = empty.name
    bpy.data.objects.remove(empty)
    return root


def top_objects(root: bpy.types.Collection) -> list[bpy.types.Object]:
    """The root's objects whose parent isn't in the root (or that have none)."""
    inside = set(root.all_objects)
    return [obj for obj in root.all_objects if obj.parent not in inside]


def placement_of(root: bpy.types.Collection) -> Matrix | None:
    """Where a made-editable copy was placed, or None for an asset started here."""
    values = root.get(PLACEMENT)
    if values is None:
        return None
    values = list(values)
    return Matrix([values[row * 4 : row * 4 + 4] for row in range(4)])


def world_matrix(obj: bpy.types.Object, view_layer: bpy.types.ViewLayer) -> Matrix:
    """An object's world matrix, worked out fresh.

    matrix_world is stale until Blender next updates (just after appending or moving
    something, say), so it isn't trusted as it is.
    """
    if obj.parent is None:
        return obj.matrix_basis.copy()
    view_layer.update()
    return obj.matrix_world.copy()


# Run in a separate Blender: libraries.write can't write scenes (Blender 5.2 crashes), so
