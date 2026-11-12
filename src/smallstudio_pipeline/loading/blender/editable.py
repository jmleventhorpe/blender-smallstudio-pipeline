"""Make Editable: swap a linked asset for a local copy to edit in whatever file it's in.

make_editable() appends the asset's latest versioned publish where the linked one was,
bakes the placing empty's transform into the copy and keeps it on the copy's root
(PLACEMENT), so in_asset_space() can move the copy back into the asset's own space while
it's checked and published. link_again() swaps the copy for a link to the asset's
hero where it stood: after publishing it (Link Back), or to throw the edits away (Back
to Link). Tested as spike T12.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import bpy
from mathutils import Matrix

from ...common.errors import PipelineError
from ...project.blender.identity import TASK, asset_identity, linked_asset
from ...project.core.entities import Asset
from ...project.core.project import Project
from ...publishing.core.publishing import relative
from ..core.updates import publish_version
from . import libraries, updates

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


@contextmanager
def in_asset_space(root: bpy.types.Collection, view_layer: bpy.types.ViewLayer) -> Iterator[None]:
    """Move a copy's objects into the asset's own space for as long as this lasts, as
    publishing it does. Objects added while editing in place are moved too."""
    placement = placement_of(root)
    if placement is None:  # Started here: the file's space is the asset's own.
        yield
        return
    to_asset = placement.inverted()
    saved = [(obj, obj.parent, obj.matrix_basis.copy()) for obj in top_objects(root)]
    try:
        for obj, _, _ in saved:
            world = world_matrix(obj, view_layer)
            obj.parent = None
            obj.matrix_basis = to_asset @ world
        view_layer.update()
        yield
    finally:
        for obj, parent, basis in saved:
            obj.parent = parent
            obj.matrix_basis = basis
        view_layer.update()


def world_matrix(obj: bpy.types.Object, view_layer: bpy.types.ViewLayer) -> Matrix:
    """An object's world matrix, worked out fresh.

    matrix_world is stale until Blender next updates (just after appending or moving
    something, say), so it isn't trusted as it is.
    """
    if obj.parent is None:
        return obj.matrix_basis.copy()
    view_layer.update()
    return obj.matrix_world.copy()


def link_again(
    root: bpy.types.Collection, asset: Asset, hero: Path, scene: bpy.types.Scene
) -> bpy.types.Object:
    """Replace a made-editable copy with the asset's hero, instanced where the copy stood."""
    homes = [c for c in scene.collection.children_recursive if root in c.children[:]]
    home = homes[0] if homes else scene.collection
    placement = placement_of(root)
    name = root.get(PLACEMENT_NAME, asset.name)

    # Remove the copy and the data only it used, so the next copy doesn't get .001 names.
    objects = list(root.all_objects)
    data = {obj.data for obj in objects if obj.data is not None}
    materials = {slot.material for obj in objects for slot in obj.material_slots if slot.material}
    bpy.data.batch_remove([*objects, *root.children_recursive, root])
    bpy.data.batch_remove([d for d in data if d.users == 0])
    bpy.data.batch_remove([m for m in materials if m.users == 0])

    # The old version is still loaded here (that's what was made editable), and linking
    # again would just hand it back: reload it, so every instance shows the new publish.
    path = relative(asset.project, hero)
    library = libraries.linked_publishes(asset.project).get(path)
    if library is not None:
        library.reload()
    linked = libraries.load_root(hero, asset.name, link=True)
    updates.seen[path] = publish_version(asset.project, path)
    empty = bpy.data.objects.new(name, None)
    home.objects.link(empty)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = linked
    if placement is not None:
        empty.matrix_world = placement
    return empty


def editable_copy(
    obj: bpy.types.Object | None, scene: bpy.types.Scene
) -> bpy.types.Collection | None:
    """The made-editable copy an object is part of, if any."""
    for collection in scene.collection.children_recursive:
        if placement_of(collection) is not None and obj in collection.all_objects[:]:
            return collection
    return None
