"""Runs inside Blender (see run.py): building a sequence's animation file from its layout."""

import bpy
import pytest
from conftest import key_x, library_load, make_cut, place, publish_model, x_at

from smallstudio_pipeline.loading.blender import instances
from smallstudio_pipeline.project.blender import nodes
from smallstudio_pipeline.project.core.metadata import CastEntry
from smallstudio_pipeline.publishing.blender import results, review
from smallstudio_pipeline.publishing.core.publishing import read_record
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


def test_a_layout_cut_and_its_shots_say_theyre_layouts(project):
    make_cut()
    bpy.ops.pipeline.add_shot()
    assert layout.cut_task() == "layout"
    found = nodes.node_of(bpy.data.collections["010_010_0010"])
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


@pytest.fixture
def blocked(project):
    """010_010's layout, published: hero overridden in 0010 with its body blocked from x=0
    to x=4, and the camera keyed from x=0 to x=1."""
    publish_model(project)
    make_cut()
    bpy.ops.pipeline.add_shot()
    scene = bpy.data.scenes["010_010_0010"]
    empty = place(project, scene, "hero")
    hero = instances.override(empty, scene, scene.view_layers[0])
    key_x(next(iter(hero.all_objects)), {101: 0, 148: 4})
    assert scene.camera is not None
    key_x(scene.camera, {101: 0, 148: 1})
    master = layout.master_scene()
    nodes.make_active(master, nodes.sequence_node(master).root)  # pyright: ignore[reportOptionalMemberAccess]
    bpy.context.window.scene = master
    assert bpy.ops.pipeline.publish() == {"FINISHED"}
    return bpy.data.filepath


def body_in(scene):
    (hero,) = instances.instances(scene)
    assert isinstance(hero.holder, bpy.types.Collection)
    return next(iter(hero.holder.all_objects))


def test_animate_keys_on_top_of_layouts_blocking(project, blocked):
    animation_file()
    scene = bpy.data.scenes["010_010_0010"]
    body = body_in(scene)
    assert x_at(body, scene, 148) == 4.0  # Layout's blocking plays.
    view_layer = scene.view_layers[0]
    for obj in view_layer.objects:
        obj.select_set(obj == body, view_layer=view_layer)
    # The stubs miss temp_override's context-manager methods.
    with bpy.context.temp_override(
        scene=scene, view_layer=view_layer, active_object=body, selected_objects=[body]
    ):  # pyright: ignore[reportGeneralTypeIssues]
        assert bpy.ops.pipeline.animate() == {"FINISHED"}
        assert not bpy.ops.pipeline.animate.poll()  # Done: it's local now.
    key_x(body, {120: 10})
    assert x_at(body, scene, 101) == 0.0 and x_at(body, scene, 120) == 10.0
    assert x_at(body, scene, 148) == 4.0
    bpy.ops.wm.save_mainfile()
    animation = bpy.data.filepath

    bpy.ops.wm.open_mainfile(filepath=blocked)  # Layout re-blocks both.
    scene = bpy.data.scenes["010_010_0010"]
    key_x(next(o for o in instances.instances(scene)[0].holder.all_objects), {148: 8})  # pyright: ignore[reportAttributeAccessIssue]
    assert scene.camera is not None
    key_x(scene.camera, {148: 3})
    master = layout.master_scene()
    nodes.make_active(master, nodes.sequence_node(master).root)  # pyright: ignore[reportOptionalMemberAccess]
    bpy.context.window.scene = master
    assert bpy.ops.pipeline.publish() == {"FINISHED"}

    bpy.ops.wm.open_mainfile(filepath=animation)
    scene = bpy.data.scenes["010_010_0010"]
    assert x_at(body_in(scene), scene, 120) == 10.0  # The animator's keys survive...
    assert x_at(body_in(scene), scene, 148) == 4.0  # ...and it no longer follows layout.
    assert scene.camera is not None and x_at(scene.camera, scene, 148) == 3.0  # Not animated.


def test_animation_publishes_each_shots_node_for_lighting(project, blocked):
    sequence = project.sequence("010_010")
    animation_file()
    scene = bpy.data.scenes["010_010_0010"]
    body = body_in(scene)
    view_layer = scene.view_layers[0]
    # The stubs miss temp_override's context-manager methods.
    with bpy.context.temp_override(
        scene=scene, view_layer=view_layer, active_object=body, selected_objects=[body]
    ):  # pyright: ignore[reportGeneralTypeIssues]
        bpy.ops.pipeline.animate()
    key_x(body, {120: 10})
    master = layout.master_scene()
    nodes.make_active(master, nodes.sequence_node(master).root)  # pyright: ignore[reportOptionalMemberAccess]
    assert bpy.ops.pipeline.publish() == {"FINISHED"}
    assert results.last is not None and results.last.published == "010_010_anim v001"

    hero = sequence.hero_path("anim")
    assert hero.is_file() and sequence.publish_path("anim", 1).is_file()
    record = read_record(hero.with_suffix(".json"))
    assert (record.entity, record.task) == ("010_010", "anim")
    assert record.checks["010_010_0010/CastMatchesLayout"] == "passed"
    with library_load(hero) as (data_from, _):
        assert "010_010_0010.anim" in data_from.collections  # With what's nested in it.

    bpy.ops.wm.read_homefile(use_empty=True)  # Lighting links a shot's animation.
    with library_load(hero, link=True) as (_, data_to):
        data_to.collections = ["010_010_0010.anim"]
    (linked,) = data_to.collections
    scene = bpy.context.scene
    scene.collection.children.link(linked)
    body = next(o for o in linked.all_objects if o.type == "MESH")
    assert x_at(body, scene, 120) == 10.0 and x_at(body, scene, 148) == 4.0


def test_a_cast_layout_didnt_publish_is_a_warning(project, published):
    animation_file()
    scene = bpy.data.scenes["010_010_0010"]
    place(project, scene, "hero")  # Into the animation node: hero_02.
    master = layout.master_scene()
    nodes.make_active(master, nodes.sequence_node(master).root)  # pyright: ignore[reportOptionalMemberAccess]
    assert bpy.ops.pipeline.publish() == {"FINISHED"}  # Warned, not blocked.
    assert results.last is not None
    assert results.last.statuses()["010_010_0010/CastMatchesLayout"] == "warning"


def test_check_shows_what_an_animation_publish_would_write(project, published):
    animation_file()
    assert bpy.ops.pipeline.check_publish() == {"FINISHED"}
    assert review.current is not None
    assert (review.current.title, review.current.writes) == ("010_010 · anim", "010_010_anim v001")
    assert [row.shot for row in review.current.shots] == ["0010", "0020"]


def test_check_updates_brings_the_cut_in_line_with_layout(project, published):
    layout_file = bpy.data.filepath
    animation_file()
    kept = bpy.data.objects.new("animators_prop", None)  # Work in a shot that stays.
    nodes.shot_node(bpy.data.scenes["010_010_0010"]).root.objects.link(kept)  # pyright: ignore[reportOptionalMemberAccess]
    bpy.ops.wm.save_mainfile()
    animation = bpy.data.filepath

    bpy.ops.wm.open_mainfile(filepath=layout_file)  # Layout adds, retimes and omits.
    master = layout.master_scene()
    sequence = project.sequence("010_010")
    first, second = layout.shot_strips(master)
    first.right_handle_offset = 8  # 0010 loses 8 frames off its tail.
    layout.omit_shot(second, sequence, master)
    master.frame_current = 1000
    layout.add_shot(sequence, master, master.frame_current)  # 0015: after 0010, before 0020.
    nodes.make_active(master, nodes.sequence_node(master).root)  # pyright: ignore[reportOptionalMemberAccess]
    assert bpy.ops.pipeline.publish() == {"FINISHED"}

    bpy.ops.wm.open_mainfile(filepath=animation)
    assert bpy.ops.pipeline.check_updates() == {"FINISHED"}
    master = layout.master_scene()
    strips = layout.shot_strips(master)
    assert [layout.strip_shot(s) for s in strips] == ["010_010_0010", "010_010_0015"]
    assert [(s.left_handle, s.right_handle - 1) for s in strips] == [(1, 40), (41, 88)]
    assert (
        bpy.data.scenes["010_010_0010"].frame_start,
        bpy.data.scenes["010_010_0010"].frame_end,
    ) == (101, 140)
    assert "010_010_0020" in bpy.data.scenes  # Omitted: its strip goes, its scene stays.
    assert "animators_prop" in bpy.data.scenes["010_010_0010"].objects
    shot = nodes.shot_node(bpy.data.scenes["010_010_0015"])
    assert shot is not None and shot.task == "anim" and shot.root.children
    added = bpy.data.scenes["010_010_0015"].render.filepath  # A playblast path of its own.
    assert added.endswith("shots/010_010_0015/anim/render/v001/010_010_0015_anim_v001_")
    assert bpy.ops.pipeline.check_updates() == {"FINISHED"}  # Nothing more to do.


def test_playblasts_go_to_each_shots_folder_for_the_workfiles_version(project, published):
    animation_file()
    folder = project.root / "shots/010_010_0010/anim/render"
    scene = bpy.data.scenes["010_010_0010"]
    assert scene.render.filepath == str(folder / "v001/010_010_0010_anim_v001_")
    bpy.ops.pipeline.version_up()
    assert scene.render.filepath == str(folder / "v002/010_010_0010_anim_v002_")
