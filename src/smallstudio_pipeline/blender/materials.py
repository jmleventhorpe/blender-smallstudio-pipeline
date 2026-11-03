"""Keeping a rig's materials in step with its model: re-applied by object name at publish."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import bpy

from . import libraries


@dataclass
class MaterialSync:
    updated: list[str] = field(default_factory=list)  # Objects whose materials changed.
    not_in_model: list[str] = field(default_factory=list)  # Objects the model doesn't have.
    slots_differ: list[str] = field(default_factory=list)  # Different slot counts: skipped.

    @property
    def summary(self) -> str:
        parts = [f"materials updated on {len(self.updated)} objects"]
        if self.not_in_model:
            parts.append(f"not in the model: {', '.join(self.not_in_model)}")
        if self.slots_differ:
            parts.append(f"material slots differ (skipped): {', '.join(self.slots_differ)}")
        return "; ".join(parts)


def sync_materials(root: bpy.types.Collection, model: Path) -> MaterialSync:
    """Give each object in root the materials its namesake has in the model publish."""
    sync = MaterialSync()
    objects = [obj for obj in root.all_objects if len(obj.material_slots)]
    wanted = model_materials(model, [obj.name for obj in objects])
    fresh = append_materials(model, sorted({name for names in wanted.values() for name in names}))

    for obj in objects:
        names = wanted.get(obj.name)
        if names is None:
            sync.not_in_model.append(obj.name)
        elif len(names) != len(obj.material_slots):
            sync.slots_differ.append(obj.name)
        else:
            for slot, name in zip(obj.material_slots, names, strict=True):
                slot.material = fresh.get(name)
            sync.updated.append(obj.name)
    return sync


def model_materials(model: Path, object_names: list[str]) -> dict[str, list[str]]:
    """The material names in each slot of the model publish's objects, by object name."""
    linked = list(libraries.load(model, "objects", object_names, link=True).values())
    found = {
        obj.name: [slot.material.name if slot.material else "" for slot in obj.material_slots]
        for obj in linked
    }
    # Only read for the names: drop the linked copies again.
    if linked:
        bpy.data.libraries.remove(linked[0].library)
    return found


def append_materials(model: Path, names: list[str]) -> dict[str, bpy.types.Material]:
    """Append materials from the model (with their images and node groups), replacing any
    local materials of the same name so syncing twice doesn't pile up copies."""
    names = [name for name in names if name]
    old = {name: bpy.data.materials.get((name, None)) for name in names}
    fresh = {}
    for name, material in libraries.load(model, "materials", names, link=False).items():
        previous = old[name]
        if previous is not None:
            previous.user_remap(material)
            bpy.data.materials.remove(previous)
        material.name = name  # Appending next to a same-named material added ".001".
        fresh[name] = material
    return fresh
