"""Shared helpers for the M0 spike scripts. Runs inside Blender 5.3, not plain Python."""

from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

import bpy
from mathutils import Euler, Vector

CHARACTER = "char"
OUTPUT = "anim_output"
BONES = ["root", "spine", "head"]

# Frame -> bone -> X rotation in degrees. Keyed in animation, compared in lighting.
POSES = {
    1: {"spine": 0, "head": 0},
    10: {"spine": 45, "head": 0},
    20: {"spine": 0, "head": 30},
}


class Checks:
    """Prints PASS/FAIL lines and fails the run at the end if anything failed."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.failures: list[str] = []

    def check(self, label: str, ok: bool, detail: str = "") -> bool:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {label}" + (f" ({detail})" if detail else ""))
        if not ok:
            self.failures.append(label)
        return ok

    def finish(self) -> None:
        if self.failures:
            # --python-exit-code 1 turns this into a non-zero exit.
            raise RuntimeError(f"{self.name}: {len(self.failures)} check(s) failed")
        print(f"{self.name}: all checks passed")


def output_dir() -> Path:
    """Return the --out folder passed after '--', or a new temp folder."""
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args, _ = parser.parse_known_args(argv)  # Scripts may take their own options too.
    # Absolute, so Blender stores sensible relative library paths.
    out = (args.out or Path(tempfile.mkdtemp(prefix="spike_"))).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"Output folder: {out}")
    return out


def step(text: str) -> None:
    print(f"\n== {text}")


# Files


def start_file(path: Path) -> None:
    """Start an empty file and save it at path, so relative links resolve from there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def open_file(path: Path) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(path))


def load_collection(path: Path, name: str) -> bpy.types.Collection:
    """Link a collection from another file without putting it in a scene."""
    with bpy.data.libraries.load(str(path), link=True, relative=True) as (_, data_to):
        data_to.collections = [name]
    return data_to.collections[0]


def link_collection(path: Path, name: str, scene: bpy.types.Scene) -> bpy.types.Collection:
    """Link a collection from another file and put it in the scene."""
    collection = load_collection(path, name)
    scene.collection.children.link(collection)
    return collection


def instance_collection(
    collection: bpy.types.Collection, name: str, parent: bpy.types.Collection
) -> bpy.types.Object:
    """Add an empty that instances collection, as a drag from the Asset Browser does."""
    empty = bpy.data.objects.new(name, None)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = collection
    parent.objects.link(empty)
    return empty


def make_override(
    linked: bpy.types.Collection, scene: bpy.types.Scene, view_layer: bpy.types.ViewLayer
) -> bpy.types.Collection:
    """Override a linked collection in the scene and remove the plain link."""
    override = linked.override_hierarchy_create(scene, view_layer, do_fully_editable=True)
    # Compare by identity: the linked collection and its override share a name.
    if any(child == linked for child in scene.collection.children):
        scene.collection.children.unlink(linked)
    return override


def write_publish(
    root: bpy.types.Collection,
    hero_path: Path,
    versioned_path: Path,
    mark: Sequence[bpy.types.Collection] = (),
) -> None:
    """Write root as a hero file with `mark` marked as assets, and an unmarked versioned copy."""
    hero_path.parent.mkdir(parents=True, exist_ok=True)
    fake_users = {collection: collection.use_fake_user for collection in mark}
    for collection in mark:
        collection.asset_mark()
        collection.asset_data.use_preferred_import_method = True
        collection.asset_data.preferred_import_method = "LINK"
    try:
        # The temp file sits next to the hero, so relative library paths stay correct
        # and the rename is atomic.
        temp_path = hero_path.with_name(f"{hero_path.stem}.tmp.blend")
        bpy.data.libraries.write(str(temp_path), {root}, path_remap="RELATIVE_ALL")
        replace_with_retry(temp_path, hero_path)
    finally:
        for collection, had_fake_user in fake_users.items():
            collection.asset_clear()
            collection.use_fake_user = had_fake_user
    bpy.data.libraries.write(str(versioned_path), {root}, path_remap="RELATIVE_ALL")


def replace_with_retry(source: Path, target: Path, attempts: int = 10, delay: float = 0.5) -> int:
    """os.replace, retried: Windows refuses it while another process has target open.

    Returns the number of attempts it took.
    """
    for attempt in range(1, attempts + 1):
        try:
            os.replace(source, target)
            return attempt
        except PermissionError as error:
            print(f"   replace attempt {attempt} failed: {error}")
            if attempt == attempts:
                raise
            time.sleep(delay)
    return attempts


def asset_collections(path: Path) -> list[str]:
    """Return the names of collections marked as assets in a file."""
    with bpy.data.libraries.load(str(path), assets_only=True) as (data_from, _):
        return list(data_from.collections)


# Character


def build_character(path: Path, extra_bone: bool = False) -> bpy.types.Collection:
    """Save a file at path holding a small skinned character in a root collection."""
    start_file(path)
    scene = bpy.context.scene
    collection = bpy.data.collections.new(CHARACTER)
    scene.collection.children.link(collection)
    collection["pipeline_asset"] = CHARACTER
    # Overrides drop custom properties their reference doesn't have, so the publish
    # declares instance_id (empty) and marks it overridable for each instance to fill in.
    collection["instance_id"] = ""
    collection.property_overridable_library_set('["instance_id"]', True)

    rig = bpy.data.objects.new(f"{CHARACTER}_rig", bpy.data.armatures.new(f"{CHARACTER}_rig"))
    collection.objects.link(rig)
    _build_bones(rig, extra_bone)

    body = bpy.data.objects.new(f"{CHARACTER}_body", _build_body_mesh(f"{CHARACTER}_body"))
    collection.objects.link(body)
    _skin(body, rig)

    bpy.ops.wm.save_mainfile()
    return collection


def _build_bones(rig: bpy.types.Object, extra_bone: bool) -> None:
    # Bones can only be added in edit mode.
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    parent = None
    for index, name in enumerate(BONES):
        bone = rig.data.edit_bones.new(name)
        bone.head = (0.0, 0.0, float(index))
        bone.tail = (0.0, 0.0, float(index + 1))
        bone.parent = parent
        bone.use_connect = parent is not None
        parent = bone
    if extra_bone:
        tail = rig.data.edit_bones.new("tail")
        tail.head = (0.0, 0.0, 0.0)
        tail.tail = (0.0, -1.0, 0.0)
        tail.parent = rig.data.edit_bones["root"]
    bpy.ops.object.mode_set(mode="OBJECT")


def _build_body_mesh(name: str, height: float = 3.0, rings: int = 13) -> bpy.types.Mesh:
    """A square tube from z=0 to height, so bending the bones visibly deforms it."""
    verts = []
    for ring in range(rings):
        z = height * ring / (rings - 1)
        verts += [(-0.2, -0.2, z), (0.2, -0.2, z), (0.2, 0.2, z), (-0.2, 0.2, z)]
    faces = []
    for ring in range(rings - 1):
        a, b = ring * 4, ring * 4 + 4
        for i in range(4):
            j = (i + 1) % 4
            faces.append((a + i, a + j, b + j, b + i))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def _skin(body: bpy.types.Object, rig: bpy.types.Object) -> None:
    groups = {name: body.vertex_groups.new(name=name) for name in BONES}
    for vert in body.data.vertices:
        bone = BONES[min(int(vert.co.z), len(BONES) - 1)]
        groups[bone].add([vert.index], 1.0, "REPLACE")
    body.parent = rig
    body.modifiers.new("Armature", "ARMATURE").object = rig


def find_object(collection: bpy.types.Collection, kind: str) -> bpy.types.Object:
    return next(obj for obj in collection.all_objects if obj.type == kind)


def key_poses(rig: bpy.types.Object) -> None:
    for frame, pose in POSES.items():
        for bone_name, degrees in pose.items():
            bone = rig.pose.bones[bone_name]
            bone.rotation_quaternion = Euler((math.radians(degrees), 0, 0)).to_quaternion()
            bone.keyframe_insert("rotation_quaternion", frame=frame)


def sample_pose(
    rig: bpy.types.Object, body: bpy.types.Object, scene: bpy.types.Scene
) -> dict[int, tuple[Vector, Vector]]:
    """World positions of the head bone tip and the top of the deformed mesh, per keyed frame."""
    samples = {}
    for frame in POSES:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        rig_eval = rig.evaluated_get(depsgraph)
        head_tip = rig_eval.matrix_world @ rig_eval.pose.bones["head"].tail
        body_eval = body.evaluated_get(depsgraph)
        mesh = body_eval.to_mesh()
        top = sum((body_eval.matrix_world @ v.co for v in mesh.vertices[-4:]), Vector()) / 4
        body_eval.to_mesh_clear()
        samples[frame] = (head_tip.copy(), top)
    return samples


def poses_match(
    expected: dict[int, tuple[Vector, Vector]], actual: dict[int, tuple[Vector, Vector]]
) -> tuple[bool, str]:
    worst = max(
        (e - a).length
        for frame in expected
        for e, a in zip(expected[frame], actual[frame], strict=True)
    )
    return worst < 1e-4, f"largest difference {worst:.6f}"


# Health


def broken_ids() -> list[str]:
    """IDs that are missing, or overrides whose reference is gone."""
    broken = []
    for datablocks in (bpy.data.collections, bpy.data.objects, bpy.data.armatures, bpy.data.meshes):
        for datablock in datablocks:
            override = datablock.override_library
            if datablock.is_missing:
                broken.append(f"{datablock.name} (missing)")
            elif override and (override.reference is None or override.reference.is_missing):
                broken.append(f"{datablock.name} (override reference missing)")
    return broken


def describe_libraries() -> None:
    for library in bpy.data.libraries:
        parent = library.parent.name if library.parent else "-"
        print(f"   library {library.filepath}  missing={library.is_missing}  parent={parent}")


# Shared shot steps (T2, T3)


def build_animation(anim_path: Path, rig_path: Path) -> dict[int, tuple[Vector, Vector]]:
    """Animation workfile: link and override the rig, key poses, gather it in an output collection.

    Leaves the file open and returns the posed samples for later comparison.
    """
    start_file(anim_path)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 20

    linked = link_collection(rig_path, CHARACTER, scene)
    override = make_override(linked, scene, bpy.context.view_layer)
    override["instance_id"] = f"{CHARACTER}_01"

    output = bpy.data.collections.new(OUTPUT)
    scene.collection.children.link(output)
    scene.collection.children.unlink(override)
    output.children.link(override)

    rig = find_object(override, "ARMATURE")
    key_poses(rig)
    expected = sample_pose(rig, find_object(override, "MESH"), scene)
    bpy.ops.wm.save_mainfile()
    return expected


def build_lighting(lighting_path: Path, anim_path: Path) -> None:
    """Lighting workfile: link the animation output collection, no overrides."""
    start_file(lighting_path)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 20
    link_collection(anim_path, OUTPUT, scene)
    bpy.ops.wm.save_mainfile()


def check_lighting(
    checks: Checks,
    lighting_path: Path,
    expected: dict[int, tuple[Vector, Vector]],
    expect_tail: bool,
) -> None:
    """Reopen lighting and check the linked animation plays and is healthy."""
    open_file(lighting_path)
    scene = bpy.context.scene
    describe_libraries()

    output = next(c for c in bpy.data.collections if c.name == OUTPUT and c.library)
    character = next(c for c in output.children if c.get("pipeline_asset") == CHARACTER)
    rig = find_object(output, "ARMATURE")
    body = find_object(output, "MESH")

    checks.check(
        "rig arrives as a linked override",
        rig.library is not None and rig.override_library is not None,
        f"from {rig.library.filepath if rig.library else 'local'}",
    )
    action = rig.animation_data.action if rig.animation_data else None
    checks.check("animation action comes through", action is not None, getattr(action, "name", ""))

    ok, detail = poses_match(expected, sample_pose(rig, body, scene))
    checks.check("rig and mesh pose match animation at keyed frames", ok, detail)

    bones = list(rig.data.bones.keys())
    label = "republished rig's new bone comes through" if expect_tail else "rig has its bones"
    checks.check(label, ("tail" in bones) == expect_tail, f"bones: {bones}")

    broken = broken_ids()
    checks.check("no missing data or broken overrides", not broken, ", ".join(broken))
    checks.check(
        "instance_id on the override root survives",
        character.get("instance_id") == f"{CHARACTER}_01",
        repr(character.get("instance_id")),
    )
