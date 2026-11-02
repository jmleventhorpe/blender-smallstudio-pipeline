"""Identity on Blender data: which asset a root collection is. Publishing reads it (M3)."""

from __future__ import annotations

import bpy

from ..core.entities import Asset

ASSET = "pipeline_asset"
ASSET_TYPE = "pipeline_asset_type"
INSTANCE_ID = "instance_id"


def create_root_collection(asset: Asset, scene: bpy.types.Scene) -> bpy.types.Collection:
    """Make the asset's root collection in the scene, carrying its identity."""
    collection = bpy.data.collections.new(asset.name)
    scene.collection.children.link(collection)
    collection[ASSET] = asset.name
    collection[ASSET_TYPE] = asset.asset_type
    # Overrides drop custom properties their reference doesn't have (spike T2), so every
    # asset declares instance_id, empty and overridable, for each instance in a shot to set.
    collection[INSTANCE_ID] = ""
    collection.property_overridable_library_set(f'["{INSTANCE_ID}"]', True)
    return collection


def asset_identity(collection: bpy.types.Collection) -> tuple[str, str] | None:
    """Return (asset name, asset type) if the collection is an asset's root, else None."""
    name, asset_type = collection.get(ASSET), collection.get(ASSET_TYPE)
    if isinstance(name, str) and isinstance(asset_type, str):
        return name, asset_type
    return None
