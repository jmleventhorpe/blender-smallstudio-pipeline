"""What stands in a shot: instances of assets, their IDs, and overriding one for posing.

An instance is an empty placing a linked asset (sets, and props left as they are) or an
override of an asset's root (characters posed in layout). Which asset it is comes from
the root's identity, readable through a link or an override. Which instance it is, its
instance ID, lives on whatever stands in the scene: the empty, or the override's root
(spike T2). Instance reads both.

number_instances() gives each instance in a shot without an ID the next one for its
asset (crate_03); the save handler calls it. override_for_posing() overrides a linked
asset where it stands, keeping its empty as a plain parent for placement (spike T5).
"""

from __future__ import annotations

from dataclasses import dataclass

import bpy

from ...core.casting import next_instance_id
from ...core.errors import PipelineError
from ...core.metadata import CastEntry
from ..identity import INSTANCE_ID, asset_identity, linked_asset


@dataclass(frozen=True)
class Instance:
    holder: bpy.types.Object | bpy.types.Collection  # Where its instance ID lives.
    asset: str
    asset_type: str

    @property
    def instance_id(self) -> str:
        """e.g. "crate_01", or "" before the shot is saved."""
        value = self.holder.get(INSTANCE_ID, "")
        return value if isinstance(value, str) else ""

    def set_instance_id(self, value: str) -> None:
        """Set the instance ID on whatever stands in the scene."""
        self.holder[INSTANCE_ID] = value


def instances(scene: bpy.types.Scene) -> list[Instance]:
    """The asset instances standing in a scene, by name of what holds them.

    Only what this file placed counts: pieces inside an overridden set are the set's.
    """
    found = []
    for obj in scene.objects:
        root = linked_asset(obj)
        identity = asset_identity(root) if root else None
        if identity and obj.library is None and obj.override_library is None:
            found.append(Instance(obj, *identity))
    roots = [c for c in scene.collection.children_recursive if c.override_library]
    asset_roots = [c for c in roots if asset_identity(c)]
    for root in asset_roots:
        inside_another = any(root in other.children_recursive[:] for other in asset_roots)
        identity = asset_identity(root)
        if identity and not inside_another:
            found.append(Instance(root, *identity))
    return sorted(found, key=lambda instance: instance.holder.name)


def number_instances(scene: bpy.types.Scene) -> list[str]:
    """Give each instance without an ID the next one for its asset. Returns the new IDs."""
    found = instances(scene)
    taken = [instance.instance_id for instance in found if instance.instance_id]
    given = []
    for instance in found:
        if not instance.instance_id:
            new = next_instance_id(instance.asset, taken)
            instance.set_instance_id(new)
            taken.append(new)
            given.append(new)
    return given


def casting(scene: bpy.types.Scene) -> tuple[CastEntry, ...]:
    """The shot's casting: each instance's asset and ID, by ID."""
    entries = [CastEntry(i.asset, i.instance_id) for i in instances(scene)]
    return tuple(sorted(entries, key=lambda entry: entry.instance_id))


def override_for_posing(
    empty: bpy.types.Object, scene: bpy.types.Scene, view_layer: bpy.types.ViewLayer
) -> bpy.types.Collection:
    """Override the linked asset an empty places, keeping the empty as its plain parent.

    Blender puts a new override at the origin and leaves the empty behind (spike T5), so
    the empty stops instancing and the override's top objects are parented to it. Only
    their parent is overridden, so a republished asset still updates. The instance ID
    moves from the empty to the override's root.
    """
    linked = linked_asset(empty)
    if linked is None:
        raise PipelineError("Select the empty that places a linked asset.")
    if not empty.get(INSTANCE_ID):
        number_instances(scene)
    instance_id = empty.get(INSTANCE_ID, "")
    homes = list(empty.users_collection)

    override = linked.override_hierarchy_create(scene, view_layer, do_fully_editable=True)
    if homes and scene.collection not in homes:  # Keep it beside its empty.
        homes[0].children.link(override)
        scene.collection.children.unlink(override)
    empty.instance_type = "NONE"
    empty.instance_collection = None
    inside = set(override.all_objects)
    for obj in override.all_objects:
        if obj.parent not in inside:
            obj.parent = empty
    override[INSTANCE_ID] = instance_id
    del empty[INSTANCE_ID]
    return override
