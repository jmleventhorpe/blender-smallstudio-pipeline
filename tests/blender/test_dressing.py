"""Runs inside Blender (see run.py): changing a linked set in whatever file it's in.

The street set holds a crate, linked and placed. In a shot, Override lets its pieces move
for that shot only; Make Editable swaps it for a copy that publishes the set itself; Back
to Link throws either away. In the set's own file, its crate can be overridden too.
"""

import bpy
from conftest import link_collection, make_cut, place, placed_at, publish_prop, save_blend

from smallstudio_pipeline.loading.blender import instances
from smallstudio_pipeline.project.blender import nodes
from smallstudio_pipeline.project.blender.identity import create_root_collection
from smallstudio_pipeline.project.core.metadata import CastEntry
from smallstudio_pipeline.session import state


def street_set(project):
    """The street set, published: a crate linked in and placed at (5, 0, 0)."""
    publish_prop(project, "crate")
    bpy.ops.wm.read_homefile(use_empty=True)
    street = project.create_asset("set", "street")
    root = create_root_collection(street, bpy.context.scene)
    nodes.make_active(bpy.context.scene, root)
    place(project, bpy.context.scene, "crate", location=(5.0, 0.0, 0.0))
    save_blend(street.workfile_path("model", 1))
    state.refresh()
    bpy.ops.pipeline.publish()
    return street


def shot_with_street(project):
    """A cut with one shot, the street placed in it and saved; returns (scene, empty)."""
    street_set(project)
    make_cut()
    bpy.ops.pipeline.add_shot()
    scene = bpy.data.scenes["010_010_0010"]
    empty = place(project, scene, "street")
    bpy.ops.wm.save_mainfile()
    return scene, empty


def act_on(scene, obj, operator):
    """Run a Pipeline operator with obj active in scene, as picking it would."""
    view_layer = scene.view_layers[0]
    # The stubs miss temp_override's context-manager methods.
    with bpy.context.temp_override(scene=scene, view_layer=view_layer, active_object=obj):  # pyright: ignore[reportGeneralTypeIssues]
        return getattr(bpy.ops.pipeline, operator)()


def piece(root, asset):
    """The empty placing an asset inside an overridden set."""
    return next(
        obj
        for obj in root.all_objects
        if obj.instance_collection and obj.instance_collection.name == asset
    )


def test_a_set_overridden_in_a_shot_can_be_dressed_there(project):
    scene, empty = shot_with_street(project)
    assert act_on(scene, empty, "override") == {"FINISHED"}
    root = next(c for c in bpy.data.collections if c.override_library and c.name == "street")
    crate = piece(root, "crate")
    crate.location.x += 3.0
    path = bpy.data.filepath
    bpy.ops.wm.save_mainfile()

    bpy.ops.wm.open_mainfile(filepath=path)
    scene = bpy.data.scenes["010_010_0010"]
    root = next(c for c in bpy.data.collections if c.override_library and c.name == "street")
    assert placed_at(piece(root, "crate")) == (8.0, 0.0, 0.0)  # Moved here, in this shot.
    assert instances.casting(scene) == (CastEntry("street", "street_01"),)  # The set's pieces.
    nodes.make_active(scene, nodes.shot_node(scene).root)  # pyright: ignore[reportOptionalMemberAccess]
    assert bpy.ops.pipeline.publish() == {"FINISHED"}

    assert act_on(scene, piece(root, "crate"), "back_to_link") == {"FINISHED"}
    assert not [c for c in bpy.data.collections if c.override_library]
    (instance,) = instances.instances(scene)
    assert (instance.asset, instance.instance_id, instance.overridden) == (
        "street",
        "street_01",
        False,
    )


def test_a_set_made_editable_in_a_shot_publishes_the_set(project):
    scene, empty = shot_with_street(project)
    street = project.asset("street")
    assert act_on(scene, empty, "make_editable") == {"FINISHED"}
    copy = next(c for c in bpy.data.collections if c.name == "street" and c.library is None)
    node = nodes.node_of(copy)
    assert node is not None and node.kind == "asset"
    assert copy in nodes.shot_node(scene).root.children[:]  # pyright: ignore[reportOptionalMemberAccess]

    nodes.make_active(scene, copy)
    bpy.context.window_manager.pipeline_link_back = True
    with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):  # pyright: ignore[reportGeneralTypeIssues]
        assert bpy.ops.pipeline.publish() == {"FINISHED"}
    assert street.latest_publish_version("model") == 2
    (instance,) = instances.instances(scene)
    assert (instance.asset, instance.overridden) == ("street", False)


def test_back_to_link_throws_a_made_editable_copy_away(project):
    scene, empty = shot_with_street(project)
    act_on(scene, empty, "make_editable")
    copy = next(c for c in bpy.data.collections if c.name == "street" and c.library is None)
    assert act_on(scene, next(iter(copy.all_objects)), "back_to_link") == {"FINISHED"}
    assert not [c for c in bpy.data.collections if c.name == "street" and c.library is None]
    (instance,) = instances.instances(scene)
    assert (
        instance.asset == "street" and project.asset("street").latest_publish_version("model") == 1
    )


def test_a_linked_asset_can_be_overridden_in_an_assets_file(project):
    street = street_set(project)
    bpy.ops.wm.open_mainfile(filepath=str(street.workfile_path("model", 1)))
    scene = bpy.context.scene
    crate = next(o for o in scene.objects if o.instance_collection)
    assert act_on(scene, crate, "override") == {"FINISHED"}
    root = next(c for c in bpy.data.collections if c.override_library and c.name == "crate")
    assert placed_at(next(iter(root.all_objects))) == (5.0, 0.0, 0.0)
    assert act_on(scene, next(iter(root.all_objects)), "back_to_link") == {"FINISHED"}
    assert crate.instance_collection is not None


def test_a_set_publishes_with_an_overridden_piece(project):
    street = street_set(project)
    bpy.ops.wm.open_mainfile(filepath=str(street.workfile_path("model", 1)))
    scene = bpy.context.scene
    act_on(scene, next(o for o in scene.objects if o.instance_collection), "override")
    root = next(c for c in bpy.data.collections if c.override_library and c.name == "crate")
    next(iter(root.all_objects)).rotation_euler.z = 1.0
    nodes.make_active(scene, bpy.data.collections["street"])
    assert bpy.ops.pipeline.publish() == {"FINISHED"}

    bpy.ops.wm.read_homefile(use_empty=True)
    linked = link_collection(street.hero_path("model"), "street")
    body = next(o for o in linked.all_objects if o.name == "crate_box")
    assert body.override_library is not None and round(body.rotation_euler.z, 4) == 1.0
