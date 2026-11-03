"""Runs inside Blender (see run.py): instance IDs in shots, and Override for Posing."""

import bpy
import pytest
from conftest import place, placed_at, publish_model, publish_prop

from smallstudio_pipeline.blender.identity import INSTANCE_ID
from smallstudio_pipeline.blender.shots import instances, layout
from smallstudio_pipeline.core.metadata import CastEntry


@pytest.fixture
def shot(project):
    """Sequence 010_010's layout file, open, with one shot; returns the shot's scene."""
    publish_model(project)
    publish_prop(project, "crate")
    bpy.ops.pipeline.new_sequence(episode="NEW", position="END")
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


def test_only_shot_scenes_are_numbered(project, shot):
    empty = place(project, layout.master_scene(), "crate")
    bpy.ops.wm.save_mainfile()
    assert INSTANCE_ID not in empty


def test_override_for_posing_keeps_the_asset_where_it_stands(project, shot):
    empty = place(project, shot, "hero", location=(2.0, 0.0, 0.0))
    bpy.ops.wm.save_mainfile()
    override = instances.override_for_posing(empty, shot, shot.view_layers[0])

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
    override = instances.override_for_posing(empty, shot, shot.view_layers[0])
    assert override[INSTANCE_ID] == "hero_01"


def test_each_kind_of_file_offers_its_own_action_for_a_linked_asset(project, shot):
    master = layout.master_scene()
    empty = place(project, master, "crate")
    bpy.context.view_layer.objects.active = empty
    assert bpy.ops.pipeline.override_for_posing.poll()
    assert not bpy.ops.pipeline.make_editable.poll()
