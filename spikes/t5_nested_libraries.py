"""T5: do lib pieces survive two levels of linking (lib -> set -> layout)?

Run:
    blender -b --factory-startup --python spikes/t5_nested_libraries.py -- --out /tmp/t5

Pass: pieces display through two levels of linking, overriding the set in a shot allows
a per-shot dressing tweak that survives reload, and lib and set republishes come through.
If it fails, set publishes make lib pieces local (append) instead of linking them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bmesh
import bpy

from spike_utils import (
    Checks,
    asset_collections,
    broken_ids,
    describe_libraries,
    instance_collection,
    load_collection,
    open_file,
    output_dir,
    start_file,
    step,
    write_publish,
)

LIB = "lib_street"
SET = "set_street"
PIECES = ["rock", "crate"]
# Dressing in the set: empty name -> (piece, location). v002 moves the crate.
DRESSING_V1 = {
    "rock_01": ("rock", (0.0, 0.0, 0.0)),
    "rock_02": ("rock", (2.0, 0.0, 0.0)),
    "crate_01": ("crate", (0.0, 3.0, 0.0)),
}
DRESSING_V2 = {**DRESSING_V1, "crate_01": ("crate", (0.0, 4.0, 0.0))}
SET_PLACEMENT = (10.0, 0.0, 0.0)

Instances = list[tuple[str, tuple[float, float, float], int]]


def cube_mesh(name: str, cuts: int = 0) -> bpy.types.Mesh:
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    if cuts:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def publish_lib(out: Path, version: int, rock_cuts: int) -> Path:
    """Lib modeling: one root collection, each child collection a piece."""
    folder = out / "assets/lib/lib_street/modeling"
    start_file(folder / f"work/lib_street_modeling_v{version:03}.blend")
    root = bpy.data.collections.new(LIB)
    bpy.context.scene.collection.children.link(root)
    root["pipeline_asset"] = LIB
    for piece in PIECES:
        collection = bpy.data.collections.new(piece)
        root.children.link(collection)
        mesh = cube_mesh(f"{piece}_geo", cuts=rock_cuts if piece == "rock" else 0)
        collection.objects.link(bpy.data.objects.new(f"{piece}_geo", mesh))
    bpy.ops.wm.save_mainfile()

    hero = folder / "publish/lib_street_modeling.blend"
    versioned = folder / f"publish/lib_street_modeling_v{version:03}.blend"
    write_publish(root, hero, versioned, mark=list(root.children))
    return hero


def publish_set(out: Path, lib_hero: Path, version: int, dressing: dict) -> Path:
    """Set modeling: dress lib pieces in with instancing empties, then publish."""
    folder = out / "assets/set/set_street/modeling"
    start_file(folder / f"work/set_street_modeling_v{version:03}.blend")
    root = bpy.data.collections.new(SET)
    bpy.context.scene.collection.children.link(root)
    root["pipeline_asset"] = SET
    root["instance_id"] = ""
    root.property_overridable_library_set('["instance_id"]', True)

    pieces = {piece: load_collection(lib_hero, piece) for piece in PIECES}
    for name, (piece, location) in dressing.items():
        instance_collection(pieces[piece], name, root).location = location
    bpy.ops.wm.save_mainfile()

    hero = folder / "publish/set_street_modeling.blend"
    versioned = folder / f"publish/set_street_modeling_v{version:03}.blend"
    write_publish(root, hero, versioned, mark=[root])
    return hero


def piece_instances() -> Instances:
    """Every lib piece drawn in the scene: (object, world position, vertex count)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    found = []
    for instance in depsgraph.object_instances:
        if instance.is_instance and instance.object.type == "MESH":
            position = tuple(round(v, 4) for v in instance.matrix_world.translation)
            vertex_count = len(instance.object.data.vertices)
            found.append((instance.object.original.name, position, vertex_count))
    return sorted(found)


def expected_instances(dressing: dict, rock_verts: int, nudge: float = 0.0) -> Instances:
    """Where the pieces should be in layout, with rock_02 nudged along X by `nudge`."""
    expected = []
    for name, (piece, (x, y, z)) in dressing.items():
        x += SET_PLACEMENT[0] + (nudge if name == "rock_02" else 0.0)
        position = (round(x, 4), y + SET_PLACEMENT[1], z + SET_PLACEMENT[2])
        expected.append((f"{piece}_geo", position, rock_verts if piece == "rock" else 8))
    return sorted(expected)


def check_scene(checks: Checks, label: str, expected: Instances) -> None:
    actual = piece_instances()
    checks.check(label, actual == expected, f"got {actual}")
    broken = broken_ids()
    checks.check("no missing data or broken overrides", not broken, ", ".join(broken))


def override_instance(empty: bpy.types.Object) -> bpy.types.Collection:
    """Override a link-only instance in a shot, keeping its placement and instance_id."""
    linked = empty.instance_collection
    override = linked.override_hierarchy_create(
        bpy.context.scene, bpy.context.view_layer, reference=empty, do_fully_editable=True
    )
    override["instance_id"] = empty["instance_id"]
    # The override lands at the origin. Keep the empty as a plain parent for placement,
    # so only `parent` is overridden and object locations still follow the set publish.
    empty.instance_type = "NONE"
    empty.instance_collection = None
    for obj in override.all_objects:
        if obj.parent is None:
            obj.parent = empty
    return override


def main() -> None:
    out = output_dir()
    checks = Checks("T5")
    layout_v001 = out / "sequences/010_010/layout/work/010_010_layout_v001.blend"
    layout_v002 = out / "sequences/010_010/layout/work/010_010_layout_v002.blend"

    step("Lib: publish two pieces, each marked as an asset in the hero")
    lib_hero = publish_lib(out, version=1, rock_cuts=0)
    pieces_listed = sorted(asset_collections(lib_hero))
    checks.check("lib hero lists each piece", pieces_listed == sorted(PIECES), str(pieces_listed))

    step("Set: link and place pieces, publish")
    set_hero = publish_set(out, lib_hero, version=1, dressing=DRESSING_V1)

    step("Layout v001: link the set (link only) and place it")
    start_file(layout_v001)
    set_collection = load_collection(set_hero, SET)
    empty = instance_collection(set_collection, SET, bpy.context.scene.collection)
    empty.location = SET_PLACEMENT
    empty["instance_id"] = f"{SET}_01"
    bpy.ops.wm.save_mainfile()
    open_file(layout_v001)
    describe_libraries()
    check_scene(
        checks, "pieces show through two levels of linking", expected_instances(DRESSING_V1, 8)
    )

    step("Layout v002: override the set for a per-shot tweak, nudge rock_02, save and reopen")
    bpy.ops.wm.save_as_mainfile(filepath=str(layout_v002))
    override = override_instance(bpy.context.scene.objects[SET])
    check_scene(checks, "overriding keeps the set's placement", expected_instances(DRESSING_V1, 8))
    rock = next(obj for obj in override.all_objects if obj.name.startswith("rock_02"))
    rock.location.x += 1.0
    bpy.ops.wm.save_mainfile()
    open_file(layout_v002)
    check_scene(
        checks, "dressing tweak survives reload", expected_instances(DRESSING_V1, 8, nudge=1.0)
    )
    override = next(c for c in bpy.data.collections if c.override_library and c.name == SET)
    checks.check("instance_id moved to the override", override.get("instance_id") == f"{SET}_01")

    step("Lib: republish with a more detailed rock, reopen both layouts")
    publish_lib(out, version=2, rock_cuts=2)
    rock_verts = len(cube_mesh("probe", cuts=2).vertices)
    open_file(layout_v001)
    check_scene(
        checks,
        "lib change comes through (link only)",
        expected_instances(DRESSING_V1, rock_verts),
    )
    open_file(layout_v002)
    check_scene(
        checks,
        "lib change comes through (overridden set), tweak holds",
        expected_instances(DRESSING_V1, rock_verts, nudge=1.0),
    )

    step("Set: republish with the crate moved, reopen both layouts")
    publish_set(out, lib_hero, version=2, dressing=DRESSING_V2)
    open_file(layout_v001)
    check_scene(
        checks,
        "set change comes through (link only)",
        expected_instances(DRESSING_V2, rock_verts),
    )
    open_file(layout_v002)
    check_scene(
        checks,
        "set change comes through (overridden set), tweak holds",
        expected_instances(DRESSING_V2, rock_verts, nudge=1.0),
    )

    checks.finish()


main()
