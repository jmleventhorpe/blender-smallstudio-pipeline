"""Runs inside Blender (see run.py): building a sequence's animation file from its layout."""

import bpy
import pytest
from conftest import make_cut, place, publish_model

from smallstudio_pipeline.loading.blender import instances
from smallstudio_pipeline.project.blender import nodes
from smallstudio_pipeline.project.blender.identity import TASK
from smallstudio_pipeline.project.core.metadata import CastEntry
from smallstudio_pipeline.shots.blender import layout


@pytest.fixture
def published(project):
    """Sequence 010_010's layout, published: hero in 0010 at (2, 0, 0), 0020 empty."""
    publish_model(project)
    make_cut()
    bpy.ops.pipeline.add_shot()
    layout.master_scene().frame_current = 1000
    bpy.ops.pipeline.add_shot()
    place(project, bpy.data.scenes["010_010_0010"], "hero", location=(2.0, 0.0, 0.0))
    assert bpy.ops.pipeline.publish() == {"FINISHED"}
    return project.sequence("010_010")


def animation_file():
    """An empty file saved as 010_010's animation workfile, with its animation built."""
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.pipeline.save_to(category="sequence", entity="010_010", task="anim")
    return bpy.ops.pipeline.new_node(kind="ANIMATION", sequence="010_010")


def test_animation_builds_the_cut_and_a_scene_per_shot(project, published):
    assert animation_file() == {"FINISHED"}
    master = layout.master_scene()
    node = nodes.sequence_node(master)
    assert node is not None and (node.name, node.task) == ("010_010", "anim")
    strips = layout.shot_strips(master)
    assert [layout.strip_shot(s) for s in strips] == ["010_010_0010", "010_010_0020"]
    assert [(s.left_handle, s.right_handle - 1) for s in strips] == [(1, 48), (49, 96)]
    assert (master.frame_start, master.frame_end) == (1, 96)

    scene = bpy.data.scenes["010_010_0010"]
    shot = nodes.shot_node(scene)
    assert shot is not None and (shot.root.name, shot.task) == ("010_010_0010.anim", "anim")
    (layout_node,) = shot.root.children
    assert layout_node.override_library is not None  # Layout's node, linked and overridden.
    assert (scene.frame_start, scene.frame_end) == (101, 148)
    assert scene.camera is not None and scene.camera.override_library is not None
    assert instances.casting(scene) == (CastEntry("hero", "hero_01"),)


def test_animation_follows_a_republished_layout(project, published):
    layout_file = bpy.data.filepath
    animation_file()
    bpy.ops.wm.save_mainfile()
    path = bpy.data.filepath

    bpy.ops.wm.open_mainfile(filepath=layout_file)
    camera = bpy.data.scenes["010_010_0010"].camera
    assert camera is not None
    camera.location.x = 5.0
    nodes.make_active(layout.master_scene(), nodes.sequence_node(layout.master_scene()).root)  # pyright: ignore[reportOptionalMemberAccess]
    assert bpy.ops.pipeline.publish() == {"FINISHED"}

    bpy.ops.wm.open_mainfile(filepath=path)
    camera = bpy.data.scenes["010_010_0010"].camera
    assert camera is not None and round(camera.location.x, 3) == 5.0


def test_animation_needs_a_layout_publish(project):
    make_cut()
    bpy.ops.pipeline.add_shot()
    with pytest.raises(RuntimeError, match="has no layout publish"):
        animation_file()


def test_animation_takes_its_shots_from_layout(project, published):
    animation_file()
    assert not bpy.ops.pipeline.add_shot.poll()
    assert bpy.ops.pipeline.back_to_cut.poll()
    with pytest.raises(RuntimeError, match="Animation can't be published yet"):
        bpy.ops.pipeline.publish()


def test_a_layout_cut_and_its_shots_say_theyre_layouts(project):
    make_cut()
    bpy.ops.pipeline.add_shot()
    assert layout.cut_task() == "layout"
    shot = bpy.data.collections["010_010_0010"]
    assert shot[TASK] == "layout"
    del shot[TASK]  # From before cut nodes carried a task: still layout's.
    found = nodes.node_of(shot)
    assert found is not None and found.task == "layout"


def test_a_character_layout_left_linked_can_be_overridden_in_animation(project, published):
    animation_file()
    scene = bpy.data.scenes["010_010_0010"]
    (hero,) = instances.instances(scene)
    assert isinstance(hero.holder, bpy.types.Object) and not hero.overridden
    assert instances.places_link(hero.holder, scene)
    view_layer = scene.view_layers[0]
    # The stubs miss temp_override's context-manager methods.
    with bpy.context.temp_override(scene=scene, view_layer=view_layer, active_object=hero.holder):  # pyright: ignore[reportGeneralTypeIssues]
        assert bpy.ops.pipeline.override() == {"FINISHED"}
    (hero,) = instances.instances(scene)
    assert hero.overridden and hero.instance_id == "hero_01"
    anim_node = nodes.shot_node(scene)
    assert anim_node is not None and hero.holder in anim_node.root.children[:]
    bpy.ops.wm.save_mainfile()

    bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
    scene = bpy.data.scenes["010_010_0010"]
    (hero,) = instances.instances(scene)
    assert hero.overridden and hero.instance_id == "hero_01"
    assert isinstance(hero.holder, bpy.types.Collection)
    empty = instances.back_to_link(hero.holder)
    (hero,) = instances.instances(scene)
    assert hero.holder == empty and not hero.overridden and hero.instance_id == "hero_01"
