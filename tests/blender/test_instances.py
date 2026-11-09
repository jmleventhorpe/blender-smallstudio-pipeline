"""Runs inside Blender (see run.py): instance IDs in shots, and Override."""

import bpy
import pytest
from conftest import make_cut, place, placed_at, publish_model, publish_prop

from smallstudio_pipeline.common.errors import PipelineError
from smallstudio_pipeline.loading.blender import instances
from smallstudio_pipeline.project.blender.identity import INSTANCE_ID
from smallstudio_pipeline.project.core.metadata import CastEntry
from smallstudio_pipeline.shots.blender import layout


@pytest.fixture
def shot(project):
    """Sequence 010_010's layout file, open, with one shot; returns the shot's scene."""
    publish_model(project)
    publish_prop(project, "crate")
    make_cut()
    bpy.ops.pipeline.add_shot()
    return bpy.data.scenes["010_010_0010"]


def test_instances_are_numbered_on_save_and_keep_their_ids(project, shot):
    place(project, shot, "crate")
    place(project, shot, "crate")
    place(project, shot, "hero")
    bpy.ops.wm.save_mainfile()
    assert instances.casting(shot) == (
        CastEntry("crate", "crate_01"),
        CastEntry("crate", "crate_02"),
        CastEntry("hero", "hero_01"),
    )
    place(project, shot, "crate")
    bpy.ops.wm.save_mainfile()
    assert [i.instance_id for i in instances.instances(shot) if i.asset == "crate"] == [
        "crate_01",
        "crate_02",
        "crate_03",
    ]


def test_instances_in_every_scene_are_numbered(project, shot):
    empty = place(project, layout.master_scene(), "crate")  # A set dressed with crates, say.
    bpy.ops.wm.save_mainfile()
    assert empty[INSTANCE_ID] == "crate_01"


def test_override_keeps_the_asset_where_it_stands(project, shot):
    empty = place(project, shot, "hero", location=(2.0, 0.0, 0.0))
    bpy.ops.wm.save_mainfile()
    override = instances.override(empty, shot, shot.view_layers[0])

    assert override.override_library is not None
    assert empty.instance_collection is None and INSTANCE_ID not in empty
    body = next(obj for obj in override.all_objects if obj.type == "MESH")
    assert body.parent == empty
    assert placed_at(body) == (2.0, 0.0, 0.0)
    (instance,) = instances.instances(shot)
    assert (instance.holder, instance.instance_id) == (override, "hero_01")

    path = bpy.data.filepath
    bpy.ops.wm.save_mainfile()
    bpy.ops.wm.open_mainfile(filepath=path)
    shot = bpy.data.scenes["010_010_0010"]
    assert instances.casting(shot) == (CastEntry("hero", "hero_01"),)


def test_an_unnumbered_asset_is_numbered_when_overridden(project, shot):
    empty = place(project, shot, "hero")
    override = instances.override(empty, shot, shot.view_layers[0])
    assert override[INSTANCE_ID] == "hero_01"


def test_a_linked_asset_can_be_overridden_or_made_editable_anywhere(project, shot):
    master = layout.master_scene()
    empty = place(project, master, "crate")
    bpy.context.view_layer.objects.active = empty
    assert bpy.ops.pipeline.override.poll() and bpy.ops.pipeline.make_editable.poll()


def test_back_to_link_undoes_override(project, shot):
    empty = place(project, shot, "hero", location=(2.0, 0.0, 0.0))
    bpy.ops.wm.save_mainfile()
    override = instances.override(empty, shot, shot.view_layers[0])
    reference = override.override_library.reference

    back = instances.back_to_link(override)

    assert back == empty and empty.instance_collection == reference
    assert empty[INSTANCE_ID] == "hero_01" and placed_at(empty) == (2.0, 0.0, 0.0)
    assert not [c for c in bpy.data.collections if c.override_library]
    assert not [o for o in bpy.data.objects if o.override_library]
    (instance,) = instances.instances(shot)
    assert (instance.holder, instance.instance_id, instance.overridden) == (empty, "hero_01", False)
    again = instances.override(empty, shot, shot.view_layers[0])  # And back again.
    assert again[INSTANCE_ID] == "hero_01"


def test_an_override_not_made_for_posing_cant_go_back(project, shot):
    empty = place(project, shot, "hero")
    override = instances.override(empty, shot, shot.view_layers[0])
    for obj in override.all_objects:
        obj.parent = None  # No longer hangs from an empty.
    with pytest.raises(PipelineError, match="wasn't made by Override"):
        instances.back_to_link(override)


def test_an_instance_is_found_from_any_of_its_parts(project, shot):
    empty = place(project, shot, "hero")
    override = instances.override(empty, shot, shot.view_layers[0])
    body = next(obj for obj in override.all_objects if obj.type == "MESH")
    for part in (body, empty):
        found = instances.instance_of(part, shot)
        assert found is not None and found.holder == override
    assert instances.instance_of(shot.camera, shot) is None


def test_override_and_back_to_link_act_on_the_selection(project, shot):
    scene = shot
    place(project, scene, "hero")
    bpy.ops.wm.save_mainfile()
    view_layer = scene.view_layers[0]
    empty = next(o for o in scene.objects if o.get("instance_id") == "hero_01")
    # The stubs miss temp_override's context-manager methods.
    with bpy.context.temp_override(scene=scene, view_layer=view_layer, active_object=empty):  # pyright: ignore[reportGeneralTypeIssues]
        assert bpy.ops.pipeline.override() == {"FINISHED"}
    override = next(c for c in bpy.data.collections if c.override_library)
    posed = next(iter(override.all_objects))
    with bpy.context.temp_override(scene=scene, view_layer=view_layer, active_object=posed):  # pyright: ignore[reportGeneralTypeIssues]
        assert bpy.ops.pipeline.back_to_link() == {"FINISHED"}
    assert empty.instance_collection is not None and empty["instance_id"] == "hero_01"
