"""What stands in a scene: instances of assets, their IDs, and overriding one.

An instance is an empty placing a linked asset (sets, and props left as they are) or an
override of an asset's root (a character posed, or a set dressed for one shot). Which
asset it is comes from the root's identity, readable through a link or an override.
Which instance it is, its instance ID, lives on whatever stands in the scene: the empty,
or the override's root (spike T2). Instance reads both.

number_instances() gives each instance in a shot without an ID the next one for its
asset (crate_03); the save handler calls it. override() overrides a linked asset
where it stands, keeping its empty as a plain parent for placement (spike T5), so it can
be posed or, for a set, its pieces moved; back_to_link() undoes it. Overriding works in
any file: where to use it is the artist's call.
"""

from __future__ import annotations

from dataclasses import dataclass

import bpy

from ...common.errors import PipelineError
from ...project.blender.identity import INSTANCE_ID, asset_identity, linked_asset
from ...project.core.metadata import CastEntry
from ..core.casting import next_instance_id


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

    @property
    def overridden(self) -> bool:
        """True for an override (posable), False for an empty placing a link."""
        return isinstance(self.holder, bpy.types.Collection)

    @property
    def library(self) -> bpy.types.Library | None:
        """The publish it comes from, as Blender's library."""
        if isinstance(self.holder, bpy.types.Object):
            root = self.holder.instance_collection
            return root.library if root else None
        override = self.holder.override_library
        reference = override.reference if override else None
        return reference.library if reference else None


def instances(scene: bpy.types.Scene) -> list[Instance]:
    """The asset instances standing in a scene, by name of what holds them.

    Pieces inside an overridden set are the set's, not the scene's. An empty that's an
    override still counts when what it's in isn't an asset: layout's empties, in an
    animation file that links and overrides layout's shot node.
    """
    roots = [c for c in scene.collection.children_recursive if c.override_library]
    asset_roots = [c for c in roots if asset_identity(c)]
    in_assets = {obj for root in asset_roots for obj in root.all_objects}
    found = []
    for obj in scene.objects:
        root = linked_asset(obj)
        identity = asset_identity(root) if root else None
        if identity and obj.library is None and obj not in in_assets:
            found.append(Instance(obj, *identity))
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


def places_link(obj: bpy.types.Object | None, scene: bpy.types.Scene) -> bool:
    """Whether an object is an empty placing a linked asset in the scene: what Make
    Editable and Override work on. Not a piece inside an overridden set."""
    return obj is not None and any(i.holder == obj for i in instances(scene))


def override(
    empty: bpy.types.Object, scene: bpy.types.Scene, view_layer: bpy.types.ViewLayer
) -> bpy.types.Collection:
    """Override the linked asset an empty places, keeping the empty as its plain parent.

    Everything in it is editable: a character's rig to pose, a set's pieces to move.

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
    home = local_home(empty, scene)

    root = linked.override_hierarchy_create(scene, view_layer, do_fully_editable=True)
    if home != scene.collection:  # Keep it beside its empty.
        home.children.link(root)
        scene.collection.children.unlink(root)
    empty.instance_type = "NONE"
    empty.instance_collection = None
    inside = set(root.all_objects)
    for obj in root.all_objects:
        if obj.parent not in inside:
            obj.parent = empty
    root[INSTANCE_ID] = instance_id
    del empty[INSTANCE_ID]
    return root


def local_home(obj: bpy.types.Object, scene: bpy.types.Scene) -> bpy.types.Collection:
    """The innermost of this file's own collections holding an object, else the scene's.

    An override's collections can't take new children, so an empty inside layout's
    overridden shot node (in an animation file) gets the animation node.
    """
    homes = [c for c in obj.users_collection if not c.library and not c.override_library]
    if homes:
        return homes[0]
    held = [
        c
        for c in scene.collection.children_recursive
        if not c.library and not c.override_library and obj in c.all_objects[:]
    ]
    inner = [c for c in held if not any(o in c.children_recursive[:] for o in held)]
    return inner[0] if inner else scene.collection


def placing_empty(override: bpy.types.Collection) -> bpy.types.Object | None:
    """The empty an override hangs from (see override())."""
    inside = set(override.all_objects)
    parents = {obj.parent for obj in override.all_objects if obj.parent not in inside}
    return parents.pop() if len(parents) == 1 and None not in parents else None


def back_to_link(override: bpy.types.Collection) -> bpy.types.Object:
    """Undo Override: the empty places the linked asset again; what was changed is lost.

    The override and the data only it used are removed; the instance ID moves back to
    the empty, so the instance stays the same one.
    """
    reference = override.override_library.reference if override.override_library else None
    empty = placing_empty(override)
    if not isinstance(reference, bpy.types.Collection) or empty is None:
        raise PipelineError(f"{override.name} wasn't made by Override, so it can't go back.")
    instance_id = override.get(INSTANCE_ID, "")
    objects = list(override.all_objects)
    data = {obj.data for obj in objects if obj.data is not None and obj.data.override_library}
    bpy.data.batch_remove([*objects, *override.children_recursive, override])
    bpy.data.batch_remove([datablock for datablock in data if datablock.users == 0])
    empty.instance_type = "COLLECTION"
    empty.instance_collection = reference
    empty[INSTANCE_ID] = instance_id
    return empty


def instance_of(obj: bpy.types.Object | None, scene: bpy.types.Scene) -> Instance | None:
    """The instance an object belongs to: its empty, or any object of its override."""
    if obj is None:
        return None
    for instance in instances(scene):
        holder = instance.holder
        if holder == obj:
            return instance
        overridden = isinstance(holder, bpy.types.Collection)
        if overridden and (obj in holder.all_objects[:] or placing_empty(holder) == obj):
            return instance
    return None
