"""Runs inside Blender (see run.py): working on assets inside other assets' files (spike T12).

A crate is linked into a street set, placed at (5, 0, 0) and turned 90° about Z. Made
editable and published from there, it must publish in its own space, not the set's; with
Link Back ticked, the set links the new publish where the copy stood.
"""

import math
from pathlib import Path

import bmesh
import bpy
import pytest
from conftest import add_cube, link_collection, save_blend

from smallstudio_pipeline.project.blender.identity import asset_identity, create_root_collection
from smallstudio_pipeline.publishing.core.publishing import hero_record
from smallstudio_pipeline.session import state


def position(obj):
    """World position, from the evaluated object: Blender doesn't write it back to linked ones."""
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return tuple(round(value, 4) for value in evaluated.matrix_world.translation)


def local_object(name):
    """The local object of that name, not a linked one with the same name."""
    return next(obj for obj in bpy.data.objects if obj.name == name and obj.library is None)


def select_only(obj):
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


@pytest.fixture
def crate(project):
    """The crate's model, published: a body sitting 0.5 up."""
    asset = project.create_asset("prop", "crate")
    bpy.ops.wm.read_homefile(use_empty=True)
    root = create_root_collection(asset, bpy.context.scene)
    add_cube(root, "crate_body").location = (0, 0, 0.5)
    save_blend(asset.workfile_path("model", 1))
    state.refresh()
    bpy.ops.pipeline.publish()
    return asset


@pytest.fixture
def placement(project, crate):
    """The street set's workfile, with the crate linked in and placed."""
    street = project.create_asset("set", "street")
    bpy.ops.wm.read_homefile(use_empty=True)
    root = create_root_collection(street, bpy.context.scene)
    empty = bpy.data.objects.new("crate_place", None)
    root.objects.link(empty)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = link_collection(crate.hero_path("model"), "crate")
    empty.location, empty.rotation_euler = (5, 0, 0), (0, 0, math.radians(90))
    save_blend(street.workfile_path("model", 1))
    state.refresh()
    select_only(empty)
    return empty


def published_positions(path, name):
    """Where each object of a published asset sits, linked into an empty file."""
    bpy.ops.wm.read_homefile(use_empty=True)
    linked = link_collection(path, name)
    bpy.context.scene.collection.children.link(linked)  # World positions need a scene.
    return {obj.name: position(obj) for obj in linked.all_objects}


def local_copy():
    return next(c for c in bpy.data.collections if c.name == "crate" and c.library is None)


def test_make_editable_gives_a_plain_local_copy_in_the_same_place(project, placement):
    bpy.ops.pipeline.make_editable()

    local = local_copy()
    assert asset_identity(local) == ("crate", "prop")
    assert local.asset_data is None
    assert local in bpy.data.collections["street"].children[:]
    body = local_object("crate_body")
    assert body.parent is None and position(body) == (5, 0, 0.5)
    assert "crate_place" not in bpy.data.objects  # Just the collection while editing.


def link_back(on=True):
    bpy.context.window_manager.pipeline_link_back = on


def test_publishing_in_place_publishes_in_the_assets_own_space(project, crate, placement):
    link_back()
    bpy.ops.pipeline.make_editable()
    body = local_object("crate_body")
    body.location.z += 0.5  # Raised by half, so 1 up in the crate's own space.
    lid = add_cube(local_copy(), "crate_lid")
    lid.location = (5, 1, 2)  # Added in place, in the set's space.
    street_file = Path(bpy.data.filepath)
    select_only(body)

    bpy.ops.pipeline.publish()

    # The set links the crate again where it was, and is saved that way.
    assert not any(c.name == "crate" and c.library is None for c in bpy.data.collections)
    bpy.ops.wm.open_mainfile(filepath=str(street_file))
    again = bpy.data.objects["crate_place"]
    assert again.instance_type == "COLLECTION" and again.instance_collection.library
    assert position(again) == (5, 0, 0)
    # Just published: no extra workfile, and the record says it came from the set's file.
    assert crate.workfile_versions("model") == [1]
    record = hero_record(crate, "model")
    assert record is not None and record.version == 2
    assert record.source == "assets/set/street/model/work/street_model_v001.blend"
    # In the crate's own space: (5, 1, 2) in the set is (1, 0, 2) for the turned crate.
    positions = published_positions(crate.hero_path("model"), "crate")
    assert positions == {"crate_body": (0, 0, 1), "crate_lid": (1, 0, 2)}


def test_without_link_back_the_copy_stays_to_keep_editing(project, crate, placement):
    link_back(False)
    bpy.ops.pipeline.make_editable()
    select_only(local_object("crate_body"))
    bpy.ops.pipeline.publish()
    assert hero_record(crate, "model").version == 2
    assert local_copy().asset_data is None and "crate_place" not in bpy.data.objects


def test_edits_still_in_edit_mode_are_published(project, crate, placement):
    link_back()
    bpy.ops.pipeline.make_editable()
    body = local_object("crate_body")
    select_only(body)
    bpy.ops.object.mode_set(mode="EDIT")
    data = body.data
    assert isinstance(data, bpy.types.Mesh)
    mesh = bmesh.from_edit_mesh(data)
    for vertex in mesh.verts:
        vertex.co.z += 1
    bmesh.update_edit_mesh(data)

    bpy.ops.pipeline.publish()  # Without leaving Edit Mode first.

    # The set shows the edit straight away, not the version loaded before.
    shown = bpy.data.objects["crate_place"].instance_collection.all_objects["crate_body"]
    assert round(max(v.co.z for v in shown.data.vertices), 4) == 1.5
    bpy.ops.wm.read_homefile(use_empty=True)
    linked = link_collection(crate.hero_path("model"), "crate")
    top = max(v.co.z for v in linked.all_objects["crate_body"].data.vertices)
    assert round(top, 4) == 1.5  # The cube's top (0.5) raised by 1.


def test_editing_again_keeps_the_names(project, crate, placement):
    link_back()
    for _ in range(2):
        select_only(bpy.data.objects["crate_place"])
        bpy.ops.pipeline.make_editable()
        assert [obj.name for obj in local_copy().all_objects] == ["crate_body"]
        local_meshes = [mesh.name for mesh in bpy.data.meshes if mesh.library is None]
        assert all(not name.startswith("crate_body.") for name in local_meshes), local_meshes
        select_only(local_object("crate_body"))
        bpy.ops.pipeline.publish()


def test_an_asset_made_inside_a_set_publishes_from_there(project, placement):
    bpy.ops.pipeline.new_node(kind="ASSET", asset="NEW", asset_type="prop", name="barrel")
    barrel = project.asset("barrel")
    root = bpy.data.collections["barrel"]
    cube = add_cube(root, "barrel_body")
    cube.location = (2, 0, 0)
    select_only(cube)

    bpy.ops.pipeline.publish()

    assert barrel.workfile_versions("model") == []  # Publishing saves no workfile of its own.
    assert published_positions(barrel.hero_path("model"), "barrel") == {"barrel_body": (2, 0, 0)}


def test_make_editable_needs_a_linked_asset(project, placement):
    plain = bpy.data.objects.new("plain", None)
    bpy.context.scene.collection.objects.link(plain)
    select_only(plain)
    with pytest.raises(RuntimeError, match="Select a linked asset"):
        bpy.ops.pipeline.make_editable()
