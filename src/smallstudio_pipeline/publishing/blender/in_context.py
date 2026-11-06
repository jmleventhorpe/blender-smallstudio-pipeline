"""Publishing an asset node in its own space, and linking the new publish back in.

A copy made by Make Editable (loading/blender/editable.py) keeps where it stood.
in_asset_space() moves it into the asset's own space while it's checked and written, and
back after. swap_for_link() replaces it with a link to its new publish, where it stood:
what Publish's Link Back option does. Tested as spike T12.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import bpy

from ...loading.blender import libraries, updates
from ...loading.blender.editable import PLACEMENT_NAME, placement_of, top_objects, world_matrix
from ...loading.core.updates import publish_version
from ...project.core.entities import Asset
from ..core.publishing import relative


@contextmanager
def in_asset_space(root: bpy.types.Collection, view_layer: bpy.types.ViewLayer) -> Iterator[None]:
    """Move the root's objects into the asset's own space for as long as this lasts.

    Objects added while editing in place are moved too.
    """
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


# the root is written on its own and a fresh Blender builds the workfile around it.
def swap_for_link(
    root: bpy.types.Collection, asset: Asset, hero: Path, scene: bpy.types.Scene
) -> bpy.types.Object:
    """Replace the local copy with its published hero, instanced where the copy was placed."""
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
