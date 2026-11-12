"""Animate: give objects their own copy of the keys they have from layout (spike T14).

In an animation file, what layout keyed (a character's blocking, a camera move) plays
from layout's action, linked from the layout publish. Blender won't key a linked action,
so animate() swaps it for a local copy, with the same slot: blocking keeps playing, new
keys go on top, and from then on that object no longer follows layout's keys. Objects
layout didn't key need nothing: keying them makes a local action anyway.
"""

from __future__ import annotations

import bpy

from ...loading.blender import instances


def to_animate(selected: list[bpy.types.Object], scene: bpy.types.Scene) -> list[bpy.types.Object]:
    """The selected objects and every part of the characters they belong to that still
    play layout's keys."""
    found: list[bpy.types.Object] = []
    for obj in selected:
        instance = instances.instance_of(obj, scene)
        holder = instance.holder if instance else None
        parts = list(holder.all_objects) if isinstance(holder, bpy.types.Collection) else [obj]
        found += [part for part in parts if part not in found and linked_action(part)]
    return found


def linked_action(obj: bpy.types.Object) -> bpy.types.Action | None:
    """The action an object plays, if it's linked from another file."""
    data = obj.animation_data
    action = data.action if data else None
    return action if action is not None and action.library is not None else None


def animate(objects: list[bpy.types.Object]) -> list[bpy.types.Action]:
    """Give each object a local copy of its linked action, keeping its slot."""
    copies = []
    for obj in objects:
        action = linked_action(obj)
        data = obj.animation_data
        if action is None or data is None:
            continue
        slot = data.action_slot
        copy = action.copy()
        data.action = copy
        if slot is not None:
            data.action_slot = copy.slots[slot.identifier]
        copies.append(copy)
    return copies
