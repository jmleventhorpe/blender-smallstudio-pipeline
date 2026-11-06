"""Identity on Blender data: the properties nodes carry, and which asset an empty places.

A node (project/blender/nodes.py) is a root collection carrying what it is. An asset
node carries the asset's name and type (ASSET, ASSET_TYPE), the task it's for (TASK),
and an empty instance_id that each instance in a shot fills in (declared overridable,
since spike T2 found overrides drop properties their reference lacks). A sequence node
carries its code (SEQUENCE), a shot node its code (SHOT). The same keys travel with
published assets, so a linked asset's root still says which asset it is.
"""

from __future__ import annotations

import bpy

from ..core.entities import Asset

ASSET = "pipeline_asset"
ASSET_TYPE = "pipeline_asset_type"
TASK = "pipeline_task"
SEQUENCE = "pipeline_sequence"
SHOT = "pipeline_shot"
INSTANCE_ID = "instance_id"


def create_root_collection(
    asset: Asset, scene: bpy.types.Scene, task: str = ""
) -> bpy.types.Collection:
    """Make an asset node in the scene: its root collection, carrying its identity and task."""
    collection = bpy.data.collections.new(asset.name)
    scene.collection.children.link(collection)
    collection[ASSET] = asset.name
    collection[ASSET_TYPE] = asset.asset_type
    collection[TASK] = task or asset.tasks[0]
    # Overrides drop custom properties their reference doesn't have (spike T2), so every
    # asset declares instance_id, empty and overridable, for each instance in a shot to set.
    collection[INSTANCE_ID] = ""
    collection.property_overridable_library_set(f'["{INSTANCE_ID}"]', True)
    return collection


def linked_asset(obj: bpy.types.Object | None) -> bpy.types.Collection | None:
    """The linked asset root an empty instances, if it is one."""
    if obj is None or obj.instance_type != "COLLECTION" or obj.instance_collection is None:
        return None
    collection = obj.instance_collection
    return collection if collection.library and asset_identity(collection) else None


def asset_identity(collection: bpy.types.Collection) -> tuple[str, str] | None:
    """Return (asset name, asset type) if the collection is an asset's root, else None."""
    name, asset_type = collection.get(ASSET), collection.get(ASSET_TYPE)
    if isinstance(name, str) and isinstance(asset_type, str):
        return name, asset_type
    return None
