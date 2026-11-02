"""T4: how long does a sequence lighting file take to open at 10, 20 and 40 shots?

Run (use a real disk for --out, not a RAM-backed /tmp):
    blender -b --factory-startup --python spikes/t4_lighting_load.py -- --out spikes/out/t4

Options: --shots 10,20,40  --characters 3  --bones 200  --verts 40000  --threshold 60

Each shot gets its own animation publish with several overrides of a generated heavy rig.
Each lighting file has a scene per shot linking that publish, plus a shared set and light
rig. Every file is then opened in a fresh Blender to measure open time, memory, the first
evaluation of three scenes and one rendered frame.

Pass: the 20-shot file opens within --threshold seconds.
If it fails, long sequences split across several lighting files, or shots load on demand.
"""

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bpy
from mathutils import Euler, Vector

from spike_utils import (
    Checks,
    instance_collection,
    load_collection,
    make_override,
    output_dir,
    start_file,
    step,
    write_publish,
)

CHARACTER = "heavy"
SET = "set_big"
LIGHT_RIG = "light_rig"
OUTPUT = "anim_output"
CHAINS = 10
KEY_FRAMES = (1, 24, 48)


def options() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", default="10,20,40")
    parser.add_argument("--characters", type=int, default=3)
    parser.add_argument("--bones", type=int, default=200)
    parser.add_argument("--verts", type=int, default=40_000)
    parser.add_argument("--threshold", type=float, default=60.0)
    parser.add_argument("--measure", action="store_true", help="internal: measure the open file")
    args, _ = parser.parse_known_args(argv)
    return args


# Building


def build_heavy_rig(path: Path, bones: int, verts: int) -> Path:
    """A rig of CHAINS bone chains with constraints, skinning a dense tube mesh."""
    start_file(path)
    collection = bpy.data.collections.new(CHARACTER)
    bpy.context.scene.collection.children.link(collection)
    collection["pipeline_asset"] = CHARACTER
    collection["instance_id"] = ""
    collection.property_overridable_library_set('["instance_id"]', True)

    rig = bpy.data.objects.new(f"{CHARACTER}_rig", bpy.data.armatures.new(f"{CHARACTER}_rig"))
    collection.objects.link(rig)
    per_chain = max(bones // CHAINS, 1)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    control = rig.data.edit_bones.new("ctrl")
    control.head, control.tail = (0, -2, 0), (0, -2, 0.5)
    for chain in range(CHAINS):
        angle = 2 * math.pi * chain / CHAINS
        offset = Vector((0.3 * math.cos(angle), 0.3 * math.sin(angle), 0))
        parent = None
        for index in range(per_chain):
            bone = rig.data.edit_bones.new(f"c{chain:02}_{index:03}")
            bone.head = offset + Vector((0, 0, index * 3 / per_chain))
            bone.tail = offset + Vector((0, 0, (index + 1) * 3 / per_chain))
            bone.parent = parent
            bone.use_connect = parent is not None
            parent = bone
    bpy.ops.object.mode_set(mode="OBJECT")
    # A constraint per chain, so evaluation isn't just plain FK.
    for chain in range(CHAINS):
        tip = rig.pose.bones[f"c{chain:02}_{per_chain - 1:03}"]
        track = tip.constraints.new("DAMPED_TRACK")
        track.target, track.subtarget = rig, "ctrl"

    body = bpy.data.objects.new(f"{CHARACTER}_body", _tube_mesh(verts))
    collection.objects.link(body)
    _skin_by_chain(body, per_chain)
    body.parent = rig
    body.modifiers.new("Armature", "ARMATURE").object = rig
    subsurf = body.modifiers.new("Subdivision", "SUBSURF")
    subsurf.levels, subsurf.render_levels = 0, 1

    bpy.ops.wm.save_mainfile()
    hero = path.parent.parent / "publish" / f"{CHARACTER}_rigging.blend"
    write_publish(
        collection, hero, hero.with_name(f"{CHARACTER}_rigging_v001.blend"), mark=[collection]
    )
    return hero


def _tube_mesh(verts: int) -> bpy.types.Mesh:
    around = 200
    rings = max(verts // around, 2)
    coords = [
        (
            0.4 * math.cos(2 * math.pi * a / around),
            0.4 * math.sin(2 * math.pi * a / around),
            3 * r / (rings - 1),
        )
        for r in range(rings)
        for a in range(around)
    ]
    faces = [
        (
            r * around + a,
            r * around + (a + 1) % around,
            (r + 1) * around + (a + 1) % around,
            (r + 1) * around + a,
        )
        for r in range(rings - 1)
        for a in range(around)
    ]
    mesh = bpy.data.meshes.new(f"{CHARACTER}_body")
    mesh.from_pydata(coords, [], faces)
    return mesh


def _skin_by_chain(body: bpy.types.Object, per_chain: int) -> None:
    """Each vertex follows the bone of its nearest chain at its height."""
    groups = {}
    members: dict[str, list[int]] = {}
    for vert in body.data.vertices:
        angle = math.atan2(vert.co.y, vert.co.x) % (2 * math.pi)
        chain = round(angle / (2 * math.pi) * CHAINS) % CHAINS
        index = min(int(vert.co.z / 3 * per_chain), per_chain - 1)
        members.setdefault(f"c{chain:02}_{index:03}", []).append(vert.index)
    for name, indices in members.items():
        groups[name] = body.vertex_groups.new(name=name)
        groups[name].add(indices, 1.0, "REPLACE")


def build_set(path: Path) -> Path:
    """A heavy static set: a dense grid."""
    start_file(path)
    collection = bpy.data.collections.new(SET)
    bpy.context.scene.collection.children.link(collection)
    collection["pipeline_asset"] = SET
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=450, y_subdivisions=450, size=40)
    ground = bpy.context.active_object
    for user in list(ground.users_collection):
        user.objects.unlink(ground)
    collection.objects.link(ground)
    bpy.ops.wm.save_mainfile()
    hero = path.parent.parent / "publish" / f"{SET}_modeling.blend"
    write_publish(collection, hero, hero.with_name(f"{SET}_modeling_v001.blend"), mark=[collection])
    return hero


def build_anim_publish(work: Path, publish: Path, rig_hero: Path, characters: int) -> None:
    """One shot's animation: several overrides of the rig, every bone keyed, then published."""
    start_file(work)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = KEY_FRAMES[0], KEY_FRAMES[-1]
    output = bpy.data.collections.new(OUTPUT)
    scene.collection.children.link(output)
    linked = load_collection(rig_hero, CHARACTER)
    for number in range(1, characters + 1):
        scene.collection.children.link(linked)
        override = make_override(linked, scene, bpy.context.view_layer)
        override["instance_id"] = f"{CHARACTER}_{number:02}"
        scene.collection.children.unlink(override)
        output.children.link(override)
        rig = next(obj for obj in override.all_objects if obj.type == "ARMATURE")
        rig.location.x = number * 2.0
        for frame in KEY_FRAMES:
            for bone in rig.pose.bones:
                bone.rotation_quaternion = Euler(
                    (0.1 * math.sin(frame + number), 0, 0)
                ).to_quaternion()
                bone.keyframe_insert("rotation_quaternion", frame=frame)
    bpy.ops.wm.save_mainfile()
    write_publish(output, publish, publish.with_name(publish.stem + "_v001.blend"))


def build_lighting(path: Path, publishes: list[Path], set_hero: Path) -> None:
    """A scene per shot linking its animation publish, the shared set and light rig."""
    start_file(path)
    set_collection = load_collection(set_hero, SET)
    light_rig = bpy.data.collections.new(LIGHT_RIG)
    for index, kind in enumerate(("SUN", "AREA", "AREA")):
        light = bpy.data.objects.new(f"light_{index}", bpy.data.lights.new(f"light_{index}", kind))
        light.location = (4 * index - 4, -6, 5)
        light_rig.objects.link(light)

    for index, publish in enumerate(publishes):
        scene = bpy.context.scene if index == 0 else bpy.data.scenes.new("shot")
        scene.name = f"{publish.parent.parent.parent.name}_lighting"
        scene.frame_start, scene.frame_end = KEY_FRAMES[0], KEY_FRAMES[-1]
        scene.collection.children.link(load_collection(publish, OUTPUT))
        instance_collection(set_collection, SET, scene.collection)
        scene.collection.children.link(light_rig)
        camera = bpy.data.objects.new(f"cam_{index:03}", bpy.data.cameras.new(f"cam_{index:03}"))
        camera.location, camera.rotation_euler = (4, -12, 3), (1.4, 0, 0.3)
        scene.collection.objects.link(camera)
        scene.camera = camera
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 1
        scene.render.resolution_x, scene.render.resolution_y = 320, 180
        scene.render.resolution_percentage = 100
    bpy.ops.wm.save_mainfile()


# Measuring (runs in a fresh Blender with the lighting file open)


def peak_memory_mb() -> float:
    status = Path("/proc/self/status").read_text()
    line = next(line for line in status.splitlines() if line.startswith("VmHWM"))
    return int(line.split()[1]) / 1024


def measure_open_file() -> None:
    scenes = sorted(bpy.data.scenes, key=lambda s: s.name)
    result = {"shots": len(scenes), "memory_after_open_mb": peak_memory_mb()}
    picks = [scenes[0], scenes[len(scenes) // 2], scenes[-1]]
    timings, object_counts = [], []
    for scene in picks:
        start = time.perf_counter()
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            scene.frame_set(24)
            depsgraph = bpy.context.evaluated_depsgraph_get()
        timings.append(time.perf_counter() - start)
        object_counts.append(len(depsgraph.objects))
    result["first_evaluation_s"] = [round(t, 2) for t in timings]
    result["objects_evaluated"] = object_counts
    start = time.perf_counter()
    bpy.ops.render.render(scene=picks[1].name)
    result["render_frame_s"] = round(time.perf_counter() - start, 2)
    result["peak_memory_mb"] = round(peak_memory_mb())
    result["memory_after_open_mb"] = round(result["memory_after_open_mb"])
    print("T4RESULT " + json.dumps(result))


def run_blender(*args: str) -> tuple[float, str]:
    start = time.perf_counter()
    done = subprocess.run(
        [bpy.app.binary_path, "-b", "--factory-startup", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return time.perf_counter() - start, done.stdout


def measure(path: Path) -> dict:
    """Open time (minus Blender's own startup), then the in-file measurements."""
    # Best of two, to keep disk cache and startup noise out of it.
    baseline = min(run_blender("--python-expr", "pass")[0] for _ in range(2))
    with_file = min(run_blender(str(path), "--python-expr", "pass")[0] for _ in range(2))
    _, stdout = run_blender(str(path), "--python", __file__, "--", "--measure")
    line = next(line for line in stdout.splitlines() if line.startswith("T4RESULT "))
    result = json.loads(line.removeprefix("T4RESULT "))
    result["open_s"] = round(with_file - baseline, 2)
    return result


def main() -> None:
    args = options()
    if args.measure:
        measure_open_file()
        return

    out = output_dir()
    checks = Checks("T4")
    counts = sorted(int(n) for n in args.shots.split(","))

    step(f"Build the heavy rig ({args.bones} bones, {args.verts} vertices) and the set")
    rig_hero = build_heavy_rig(
        out / "assets/character/heavy/rigging/work/heavy_rigging_v001.blend", args.bones, args.verts
    )
    set_hero = build_set(out / "assets/set/set_big/modeling/work/set_big_modeling_v001.blend")

    step(f"Build {counts[-1]} animation publishes, {args.characters} characters each")
    publishes = []
    start = time.perf_counter()
    for number in range(1, counts[-1] + 1):
        shot = f"010_010_{number * 10:04}"
        folder = out / f"shots/{shot}/animation"
        publish = folder / f"publish/{shot}_animation.blend"
        build_anim_publish(
            folder / f"work/{shot}_animation_v001.blend", publish, rig_hero, args.characters
        )
        publishes.append(publish)
    print(f"   built in {time.perf_counter() - start:.0f}s")

    results = []
    for count in counts:
        step(f"Lighting file with {count} shots: build, then open in a fresh Blender")
        lighting = out / f"sequences/010_010/lighting/work/010_010_lighting_{count:02}shots.blend"
        build_lighting(lighting, publishes[:count], set_hero)
        result = measure(lighting)
        result["file_mb"] = round(lighting.stat().st_size / 1e6, 1)
        print(f"   {result}")
        results.append(result)

    step(
        f"Republish the rig with more bones, then reopen the {counts[-1]}-shot file (forces resync)"
    )
    build_heavy_rig(
        out / "assets/character/heavy/rigging/work/heavy_rigging_v002.blend",
        args.bones + CHAINS,
        args.verts,
    )
    resync = measure(lighting)
    resync["after_rig_republish"] = True
    print(f"   {resync}")
    results.append(resync)

    (out / "t4_results.json").write_text(json.dumps(results, indent=2))
    twenty = next((r for r in results if r["shots"] == 20), results[-1])
    checks.check(
        f"{twenty['shots']}-shot file opens within {args.threshold:.0f}s",
        twenty["open_s"] <= args.threshold,
        f"{twenty['open_s']}s",
    )
    checks.check(
        f"{counts[-1]}-shot file opens within {args.threshold:.0f}s after a rig republish",
        resync["open_s"] <= args.threshold,
        f"{resync['open_s']}s",
    )
    checks.finish()


main()
