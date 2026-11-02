"""T6: can one file hold separate overrides of the same character in several scenes?

Run:
    blender -b --factory-startup --python spikes/t6_shared_character.py -- --out /tmp/t6

Pass: each scene keeps its own pose; the instance_id property on each override root
survives save, reload and a rig republish (override resync).
If instance_id doesn't survive, instances use a local wrapper collection instead.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bpy
from bpy_extras import anim_utils
from mathutils import Euler

from spike_utils import (
    CHARACTER,
    Checks,
    broken_ids,
    build_character,
    find_object,
    load_collection,
    make_override,
    open_file,
    output_dir,
    start_file,
    step,
)

# Shot scene -> spine angle in degrees for that shot's blocking pose.
SHOTS = {"010_010_0010": 10, "010_010_0020": 20, "010_010_0030": 30}


def character_in(scene: bpy.types.Scene) -> bpy.types.Collection:
    return next(
        child
        for child in scene.collection.children
        if child.override_library and child.get("pipeline_asset") == CHARACTER
    )


def spine_angle(rig: bpy.types.Object, frame: int) -> float:
    """Spine X rotation in degrees at frame, read from the rig's own action."""
    animation = rig.animation_data
    channelbag = anim_utils.action_get_channelbag_for_slot(animation.action, animation.action_slot)
    curves = [
        curve
        for curve in channelbag.fcurves
        if curve.data_path == 'pose.bones["spine"].rotation_quaternion'
    ]
    w, x = (curve.evaluate(frame) for curve in sorted(curves, key=lambda c: c.array_index)[:2])
    return math.degrees(2 * math.atan2(x, w))


def build_layout(path: Path, rig_path: Path) -> None:
    """One scene per shot, each with its own override of the same linked character."""
    start_file(path)
    bpy.context.scene.name = next(iter(SHOTS))
    for code in list(SHOTS)[1:]:
        bpy.data.scenes.new(code)

    linked = load_collection(rig_path, CHARACTER)
    for code, degrees in SHOTS.items():
        scene = bpy.data.scenes[code]
        scene.collection.children.link(linked)
        override = make_override(linked, scene, scene.view_layers[0])
        override["instance_id"] = f"{CHARACTER}_01"
        bone = find_object(override, "ARMATURE").pose.bones["spine"]
        bone.rotation_quaternion = Euler((math.radians(degrees), 0, 0)).to_quaternion()
        bone.keyframe_insert("rotation_quaternion", frame=1)
    bpy.ops.wm.save_mainfile()


def check_layout(checks: Checks, path: Path, expect_tail: bool) -> None:
    open_file(path)
    characters = {code: character_in(bpy.data.scenes[code]) for code in SHOTS}
    rigs = {code: find_object(collection, "ARMATURE") for code, collection in characters.items()}
    print(
        "   names per scene:", {code: (c.name, rigs[code].name) for code, c in characters.items()}
    )

    checks.check(
        "each scene has its own override",
        len({c.session_uid for c in characters.values()}) == len(SHOTS),
    )
    for code, degrees in SHOTS.items():
        angle = spine_angle(rigs[code], frame=1)
        checks.check(f"{code} keeps its own pose", abs(angle - degrees) < 1e-3, f"{angle:.3f} deg")
        checks.check(
            f"{code} instance_id survives",
            characters[code].get("instance_id") == f"{CHARACTER}_01",
            repr(characters[code].get("instance_id")),
        )
    if expect_tail:
        bones_ok = all("tail" in rig.data.bones for rig in rigs.values())
        checks.check("rig republish reaches every scene", bones_ok)
    broken = broken_ids()
    checks.check("no missing data or broken overrides", not broken, ", ".join(broken))


def main() -> None:
    out = output_dir()
    checks = Checks("T6")
    rig_path = out / "assets/character/char/rigging/publish/char_rigging.blend"
    layout = out / "sequences/010_010/layout/work/010_010_layout_v001.blend"

    step("Build the rig")
    build_character(rig_path)

    step("Layout: override the character separately in three shot scenes, pose each")
    build_layout(layout, rig_path)
    check_layout(checks, layout, expect_tail=False)

    step("Republish the rig with an extra bone, reopen, save and reopen again")
    build_character(rig_path, extra_bone=True)
    check_layout(checks, layout, expect_tail=True)
    bpy.ops.wm.save_mainfile()
    check_layout(checks, layout, expect_tail=True)

    checks.finish()


main()
