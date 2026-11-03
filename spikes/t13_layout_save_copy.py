"""T13: can a layout publish be a Save Copy of the whole workfile?

Run:
    blender -b --factory-startup --python spikes/t13_layout_save_copy.py -- --out /tmp/t13

libraries.write crashes on scenes in Blender 5.2.2, so a sequence layout file (a master
scene with scene strips, a scene per shot) can't be published the way assets are. This
checks wm.save_as_mainfile(copy=True) instead.

Pass: the copy opens with every scene, the cut's strips, the linked set and each shot's
overridden character (pose, placement under its empty, instance_id); its library paths
resolve from the publish folder; the session stays on the workfile, unchanged; and a
hero written through a temp file and a rename works the same.
"""

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bpy
from bpy_extras import anim_utils
from mathutils import Euler, Vector

from spike_utils import (
    CHARACTER,
    Checks,
    broken_ids,
    build_character,
    describe_libraries,
    find_object,
    instance_collection,
    load_collection,
    open_file,
    output_dir,
    start_file,
    step,
    write_publish,
)

SET = "street"
# Shot scene -> (spine angle in degrees, where the character's empty stands).
SHOTS = {"010_010_0010": (10, (2.0, 0.0, 0.0)), "010_010_0020": (20, (0.0, 3.0, 0.0))}
MASTER = "010_010_cut"
SHOT_LENGTH = 24


def build_set(path: Path) -> None:
    """A set publish: a root collection holding one cube."""
    start_file(path.with_name("street_model_v001.blend"))
    root = bpy.data.collections.new(SET)
    bpy.context.scene.collection.children.link(root)
    root["pipeline_asset"] = SET
    mesh = bpy.data.meshes.new("ground")
    mesh.from_pydata([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [], [(0, 1, 2, 3)])
    root.objects.link(bpy.data.objects.new("ground", mesh))
    bpy.ops.wm.save_mainfile()
    write_publish(root, path, path.with_name("street_model_v001_pub.blend"), mark=[root])


def override_under_empty(
    linked: bpy.types.Collection, scene: bpy.types.Scene, location: tuple[float, float, float]
) -> bpy.types.Collection:
    """The T5 recipe: override the character, keep the placing empty as a plain parent."""
    empty = instance_collection(linked, f"{CHARACTER}_place", scene.collection)
    empty.location = location
    view_layer = scene.view_layers[0]
    override = linked.override_hierarchy_create(scene, view_layer, do_fully_editable=True)
    empty.instance_type = "NONE"
    empty.instance_collection = None
    inside = set(override.all_objects)
    for obj in override.all_objects:
        if obj.parent not in inside:
            obj.parent = empty
    override["instance_id"] = f"{CHARACTER}_01"
    return override


def build_layout(path: Path, rig_path: Path, set_path: Path) -> None:
    """A master scene cutting two shot scenes, each with the set and a posed character."""
    start_file(path)
    master = bpy.context.scene
    master.name = MASTER
    linked_set = load_collection(set_path, SET)
    linked_character = load_collection(rig_path, CHARACTER)
    editor = master.sequence_editor_create()
    for index, (code, (degrees, location)) in enumerate(SHOTS.items()):
        scene = bpy.data.scenes.new(code)
        scene["pipeline_shot"] = code
        scene.frame_start, scene.frame_end = 101, 101 + SHOT_LENGTH - 1
        camera = bpy.data.objects.new(f"cam_{code}", bpy.data.cameras.new(f"cam_{code}"))
        scene.collection.objects.link(camera)
        scene.camera = camera
        set_empty = instance_collection(linked_set, f"{SET}_place", scene.collection)
        set_empty["instance_id"] = f"{SET}_01"
        override = override_under_empty(linked_character, scene, location)
        bone = find_object(override, "ARMATURE").pose.bones["spine"]
        bone.rotation_quaternion = Euler((math.radians(degrees), 0, 0)).to_quaternion()
        bone.keyframe_insert("rotation_quaternion", frame=101)
        strip = editor.strips.new_scene(code, scene, channel=1, frame_start=1 + index * SHOT_LENGTH)
        strip.scene_camera = camera
    master.frame_start, master.frame_end = 1, SHOT_LENGTH * len(SHOTS)
    bpy.ops.wm.save_mainfile()


def save_copy(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True, relative_remap=True)


def character_in(scene: bpy.types.Scene) -> bpy.types.Collection:
    return next(
        child
        for child in scene.collection.children
        if child.override_library and child.get("pipeline_asset") == CHARACTER
    )


def spine_angle(rig: bpy.types.Object, frame: int) -> float:
    """Spine X rotation in degrees at frame, read from the rig's own action (as in T6)."""
    animation = rig.animation_data
    channelbag = anim_utils.action_get_channelbag_for_slot(animation.action, animation.action_slot)
    curves = [
        curve
        for curve in channelbag.fcurves
        if curve.data_path == 'pose.bones["spine"].rotation_quaternion'
    ]
    w, x = (curve.evaluate(frame) for curve in sorted(curves, key=lambda c: c.array_index)[:2])
    return math.degrees(2 * math.atan2(x, w))


def placed_at(obj: bpy.types.Object) -> Vector:
    """Where an object stands, from the stored transforms up its parent chain.

    Only the active scene is evaluated in background mode, so a shot scene's
    matrix_world is stale; work it out from each object's own transform instead.
    """
    matrix = obj.matrix_basis.copy()
    while obj.parent is not None:
        matrix = obj.parent.matrix_basis @ obj.matrix_parent_inverse @ matrix
        obj = obj.parent
    return matrix.translation


def check_publish(checks: Checks, path: Path, label: str) -> None:
    """Open a published copy and check it holds the whole layout, healthy."""
    open_file(path)
    describe_libraries()
    names = {scene.name for scene in bpy.data.scenes}
    checks.check(f"{label}: every scene is there", names == {MASTER, *SHOTS}, str(sorted(names)))

    strips = bpy.data.scenes[MASTER].sequence_editor.strips
    targets = {strip.name: strip.scene.name if strip.scene else None for strip in strips}
    checks.check(
        f"{label}: the cut's strips point at their shot scenes",
        targets == {code: code for code in SHOTS},
        str(targets),
    )
    missing = [lib.filepath for lib in bpy.data.libraries if lib.is_missing]
    absolute = [lib.filepath for lib in bpy.data.libraries if not lib.filepath.startswith("//")]
    checks.check(f"{label}: libraries resolve from the publish folder", not missing, str(missing))
    checks.check(f"{label}: library paths are relative", not absolute, str(absolute))

    for code, (degrees, location) in SHOTS.items():
        scene = bpy.data.scenes[code]
        character = character_in(scene)
        rig = find_object(character, "ARMATURE")
        angle = spine_angle(rig, 101)
        checks.check(
            f"{label}: {code} keeps its pose", abs(angle - degrees) < 1e-3, f"{angle:.3f} deg"
        )
        where = placed_at(rig)
        parent = rig.parent.name if rig.parent else None
        checks.check(
            f"{label}: {code} character stands under its empty",
            (where - Vector(location)).length < 1e-4 and rig.parent is not None,
            f"{tuple(round(v, 3) for v in where)}, parent {parent}",
        )
        checks.check(
            f"{label}: {code} instance_id survives",
            character.get("instance_id") == f"{CHARACTER}_01",
            repr(character.get("instance_id")),
        )
        set_empties = [o for o in scene.objects if o.instance_collection is not None]
        checks.check(
            f"{label}: {code} set is linked and placed",
            len(set_empties) == 1 and set_empties[0].instance_collection.library is not None,
        )
    broken = broken_ids()
    checks.check(f"{label}: no missing data or broken overrides", not broken, ", ".join(broken))


def main() -> None:
    out = output_dir()
    checks = Checks("T13")
    rig_path = out / "assets/character/char/rig/publish/char_rig.blend"
    set_path = out / "assets/set/street/model/publish/street_model.blend"
    workfile = out / "sequences/010_010/layout/work/010_010_layout_v001.blend"
    versioned = out / "sequences/010_010/layout/publish/010_010_layout_v001.blend"
    hero = out / "sequences/010_010/layout/publish/010_010_layout.blend"

    step("Build a character, a set and a two-shot layout file")
    build_character(rig_path)
    build_set(set_path)
    build_layout(workfile, rig_path, set_path)

    step("Publish with Save Copy, from a session with unsaved changes")
    calls = []

    def note(*_args: object) -> None:
        calls.append(bpy.data.filepath)

    bpy.app.handlers.save_pre.append(note)
    bpy.app.handlers.save_post.append(note)
    bpy.data.scenes[MASTER].frame_current = 7  # An unsaved change.
    was_dirty = bpy.data.is_dirty
    save_copy(versioned)
    temp = hero.with_name(f"{hero.stem}.tmp.blend")
    save_copy(temp)
    os.replace(temp, hero)
    bpy.app.handlers.save_pre.remove(note)
    bpy.app.handlers.save_post.remove(note)

    checks.check(
        "the session stays on the workfile", Path(bpy.data.filepath) == workfile, bpy.data.filepath
    )
    checks.check(
        "unsaved changes stay unsaved", bpy.data.is_dirty == was_dirty, f"dirty={bpy.data.is_dirty}"
    )
    print(f"   save handlers ran {len(calls)} times, seeing filepath {set(calls)}")
    checks.check("both files were written", versioned.is_file() and hero.is_file())

    step("Open the versioned copy, then the hero")
    check_publish(checks, versioned, "versioned")
    check_publish(checks, hero, "hero")

    step("Reopen the workfile: the unsaved change was never saved there")
    open_file(workfile)
    checks.check(
        "the workfile is as it was last saved",
        bpy.data.scenes[MASTER].frame_current != 7,
        f"frame {bpy.data.scenes[MASTER].frame_current}",
    )

    checks.finish()


main()
