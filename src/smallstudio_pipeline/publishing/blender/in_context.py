"""Publishing an asset node in its own space, and linking the new publish back in.

A copy made by Make Editable (loading/blender/editable.py) keeps where it stood.
in_asset_space() moves it into the asset's own space while it's checked and written, and
back after. Publish's Link Back option then links the new publish where it stood
(loading/blender/editable.link_again). Tested as spike T12.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import bpy

from ...loading.blender.editable import placement_of, top_objects, world_matrix


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
