"""T14: can animation link a shot's node from the layout publish and override it, so
nothing is copied and layout changes keep coming through?

Run:
    blender -b --factory-startup --python spikes/t14_link_layout.py -- --out /tmp/t14

Options: --shots 10 (for the sequence-sized timing), --characters 3

Layout holds a shot node with a camera and an overridden character, blocked with keys.
Animation links that node from the layout publish and overrides it: an override of
layout's override. The animator keys the head. Layout is then republished with the
camera and character moved and a prop added. Animation must show layout's changes,
keep the animator's keys, and report nothing broken; its publish must play in lighting.
Last, a sequence-sized animation file (a scene per shot, each linking its shot node) is
opened in a fresh Blender and timed.

Pass: all the above. If it fails, animation copies from the layout publish instead.
"""

import argparse
import math
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bpy
from mathutils import Euler

from spike_utils import (
    CHARACTER,
    Checks,
    broken_ids,
    build_character,
    describe_libraries,
    find_object,
    link_collection,
    load_collection,
    make_override,
    open_file,
    output_dir,
    start_file,
    step,
)

SHOT = "010_010_0010"
PROP = "crate"


def options() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", type=int, default=10)
    parser.add_argument("--characters", type=int, default=3)
    args, _ = parser.parse_known_args(argv)
    return args


def build_prop(path: Path) -> None:
    """A prop's publish: one cube in a root collection."""
    start_file(path)
    root = bpy.data.collections.new(PROP)
    bpy.context.scene.collection.children.link(root)
    mesh = bpy.data.meshes.new(PROP)
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
    root.objects.link(bpy.data.objects.new(PROP, mesh))
    bpy.ops.wm.save_mainfile()


def rotate(rig: bpy.types.Object, bone: str, degrees: float, frame: int) -> None:
    pose_bone = rig.pose.bones[bone]
    pose_bone.rotation_quaternion = Euler((math.radians(degrees), 0, 0)).to_quaternion()
    pose_bone.keyframe_insert("rotation_quaternion", frame=frame)


def shot_node(scene: bpy.types.Scene, code: str, rig_path: Path, characters: int) -> None:
    """A shot node in scene: a camera and overridden characters, blocked with keys."""
    node = bpy.data.collections.new(code)
    node["pipeline_shot"] = code
    scene.collection.children.link(node)
    camera = bpy.data.objects.new(f"{code}_cam", bpy.data.cameras.new(f"{code}_cam"))
    camera.location = (0, -10, 2)
    node.objects.link(camera)
    scene.camera = camera
    for index in range(characters):
        linked = link_collection(rig_path, CHARACTER, scene)
        override = make_override(linked, scene, scene.view_layers[0])
        override["instance_id"] = f"{CHARACTER}_{index + 1:02d}"
        scene.collection.children.unlink(override)
        node.children.link(override)
        rig = find_object(override, "ARMATURE")
        rig.location.x = index * 2.0
        rotate(rig, "spine", 0, 1)  # Blocking.
        rotate(rig, "spine", 30, 20)


def layout_file(work: Path, publish: Path, rig_path: Path, shots: list[str], characters: int):
    start_file(work)
    first = bpy.context.scene
    for index, code in enumerate(shots):
        scene = first if index == 0 else bpy.data.scenes.new(code)
        scene.name = code
        scene.frame_start, scene.frame_end = 1, 20
        shot_node(scene, code, rig_path, characters)
    bpy.ops.wm.save_mainfile()
    publish.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(publish), copy=True)  # As the pipeline does.


def link_shot(scene: bpy.types.Scene, layout_publish: Path, code: str) -> bpy.types.Collection:
    """Link a shot node from the layout publish into scene and override it."""
    linked = link_collection(layout_publish, code, scene)
    return make_override(linked, scene, scene.view_layers[0])


def rig_in(node: bpy.types.Collection, instance_id: str) -> bpy.types.Object:
    character = next(c for c in node.children_recursive if c.get("instance_id") == instance_id)
    return find_object(character, "ARMATURE")


def evaluated(obj: bpy.types.Object) -> bpy.types.Object:
    return obj.evaluated_get(bpy.context.evaluated_depsgraph_get())


def bone_x(rig: bpy.types.Object, bone: str, scene: bpy.types.Scene, frame: int) -> float:
    """A pose bone's X rotation in degrees at a frame, as evaluated."""
    scene.frame_set(frame)
    quaternion = evaluated(rig).pose.bones[bone].rotation_quaternion
    return round(math.degrees(quaternion.to_euler().x), 2)


def main() -> None:
    out = output_dir()
    args = options()
    checks = Checks("T14")
    rig_path = out / "assets/character/char/rig/publish/char_rig.blend"
    prop_path = out / "assets/prop/crate/model/publish/crate_model.blend"
    layout_work = out / "sequences/010_010/layout/work/010_010_layout_v001.blend"
    layout_publish = out / "sequences/010_010/layout/publish/010_010_layout.blend"
    anim_work = out / f"shots/{SHOT}/anim/work/{SHOT}_anim_v001.blend"
    anim_publish = out / f"shots/{SHOT}/anim/publish/{SHOT}_anim.blend"
    lighting = out / "sequences/010_010/light/work/010_010_light_v001.blend"

    step("Publish a rig and a prop; layout blocks one shot and publishes")
    build_character(rig_path)
    build_prop(prop_path)
    layout_file(layout_work, layout_publish, rig_path, [SHOT], 1)

    step("Animation: link the shot node from the layout publish, override it, key the head")
    start_file(anim_work)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 20
    node = link_shot(scene, layout_publish, SHOT)
    describe_libraries()
    rig = rig_in(node, f"{CHARACTER}_01")
    reference = rig.override_library.reference if rig.override_library else None
    checks.check(
        "the rig is an override of layout's override",
        reference is not None and reference.override_library is not None,
        f"reference from {reference.library.filepath if reference and reference.library else '?'}",
    )
    camera = next(o for o in node.all_objects if o.type == "CAMERA")
    checks.check("the camera comes through, overridden", camera.override_library is not None)
    checks.check("layout's blocking plays", bone_x(rig, "spine", scene, 20) == 30.0)
    action = rig.animation_data.action if rig.animation_data else None
    print(f"   action {action.name if action else None}, linked={bool(action and action.library)}")

    def animator_keys() -> bool:
        """Key the head at two frames; True if both play back (really keyed)."""
        rotate(rig, "head", 0, 1)
        rotate(rig, "head", 45, 10)
        return bone_x(rig, "head", scene, 1) == 0.0 and bone_x(rig, "head", scene, 10) == 45.0

    if animator_keys():
        how = "keyed straight onto layout's action"
    else:
        assert action is not None
        copy = action.copy()  # Local, so it can take keys; layout's keys come with it.
        slot = rig.animation_data.action_slot
        rig.animation_data.action = copy
        if slot is not None:
            rig.animation_data.action_slot = copy.slots[slot.identifier]
        how = "keyed onto a local copy of layout's action" if animator_keys() else "not keyed"
    print(f"   {how}")
    checks.check(
        "layout's blocking still plays after keying", bone_x(rig, "spine", scene, 20) == 30.0
    )
    checks.check(
        "the animator's keys play",
        bone_x(rig, "head", scene, 1) == 0.0 and bone_x(rig, "head", scene, 10) == 45.0,
    )
    bpy.ops.wm.save_mainfile()

    step("Layout v2: move the camera and the character, add a prop; republish")
    open_file(layout_work)
    layout_node = bpy.data.collections[SHOT]
    next(o for o in layout_node.all_objects if o.type == "CAMERA").location.x = 5.0
    rig_in(layout_node, f"{CHARACTER}_01").location.y = 3.0
    prop = load_collection(prop_path, PROP)
    layout_node.children.link(prop)
    bpy.ops.wm.save_mainfile()
    bpy.ops.wm.save_as_mainfile(filepath=str(layout_publish), copy=True)

    step("Reopen animation")
    open_file(anim_work)
    scene = bpy.context.scene
    node = next(c for c in bpy.data.collections if c.name == SHOT and c.override_library)
    rig = rig_in(node, f"{CHARACTER}_01")
    camera = next(o for o in node.all_objects if o.type == "CAMERA")
    checks.check("layout's camera move comes through", round(camera.location.x, 3) == 5.0)
    checks.check("layout's character move comes through", round(rig.location.y, 3) == 3.0)
    checks.check(
        "layout's new prop comes through",
        any(c.name == PROP for c in node.children_recursive),
        ", ".join(c.name for c in node.children_recursive),
    )
    checks.check(
        "the animator's keys survive",
        bone_x(rig, "head", scene, 1) == 0.0 and bone_x(rig, "head", scene, 10) == 45.0,
    )
    checks.check(
        "instance_id survives two levels of override",
        node.children_recursive[0].get("instance_id") == f"{CHARACTER}_01"
        or any(c.get("instance_id") == f"{CHARACTER}_01" for c in node.children_recursive),
    )
    broken = broken_ids()
    checks.check("no missing data or broken overrides", not broken, ", ".join(broken))

    step("Publish animation (the overridden shot node) and link it in lighting")
    anim_publish.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(anim_publish), {node}, path_remap="RELATIVE_ALL")
    start_file(lighting)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 20
    link_collection(anim_publish, SHOT, scene)
    bpy.ops.wm.save_mainfile()
    open_file(lighting)
    scene = bpy.context.scene
    linked = next(c for c in bpy.data.collections if c.name == SHOT and c.library)
    rig = rig_in(linked, f"{CHARACTER}_01")
    checks.check(
        "lighting plays the animator's keys",
        bone_x(rig, "head", scene, 1) == 0.0 and bone_x(rig, "head", scene, 10) == 45.0,
    )
    checks.check("lighting plays layout's blocking", bone_x(rig, "spine", scene, 20) == 30.0)
    broken = broken_ids()
    checks.check("lighting has nothing broken", not broken, ", ".join(broken))

    step(f"A sequence animation file: {args.shots} shots, {args.characters} characters each")
    codes = [f"010_010_{(index + 1) * 10:04d}" for index in range(args.shots)]
    seq_layout = out / "seq/layout_work.blend"
    seq_publish = out / "seq/layout_publish.blend"
    seq_anim = out / "seq/anim.blend"
    layout_file(seq_layout, seq_publish, rig_path, codes, args.characters)
    start_file(seq_anim)
    for index, code in enumerate(codes):
        scene = bpy.context.scene if index == 0 else bpy.data.scenes.new(code)
        scene.name = code
        link_shot(scene, seq_publish, code)
    bpy.ops.wm.save_mainfile()
    timing = open_time(seq_anim) - open_time(None)
    print(f"   opens in {timing:.2f} s")
    print("   " + loaded(seq_anim))
    checks.check(f"the {args.shots}-shot animation file opens within 10 s", timing < 10.0)

    checks.finish()


def loaded(path: Path) -> str:
    """What a fresh Blender finds on opening path: scenes and overridden rigs."""
    expr = (
        "import bpy; rigs = [o for o in bpy.data.objects if o.type == 'ARMATURE' and "
        "o.override_library]; print('LOADED', len(bpy.data.scenes), 'scenes,', len(rigs), "
        "'overridden rigs,', len([r for r in rigs if r.animation_data and "
        "r.animation_data.action]), 'with actions')"
    )
    command = [bpy.app.binary_path, "-b", "--factory-startup", str(path), "--python-expr", expr]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return next(line for line in result.stdout.splitlines() if line.startswith("LOADED"))


def open_time(path: Path | None) -> float:
    """Wall time for a fresh Blender to open path (or nothing) and quit."""
    command = [bpy.app.binary_path, "-b", "--factory-startup"]
    if path is not None:
        command.append(str(path))
    command += ["--python-expr", "import bpy"]
    started = time.perf_counter()
    subprocess.run(command, check=True, capture_output=True)
    return time.perf_counter() - started


main()
