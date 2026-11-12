"""Runs inside Blender (see run.py): building a sequence's lighting file."""

import bpy
import pytest
from conftest import make_cut, new_file, place, publish_cut, publish_model

from smallstudio_pipeline.lighting.blender import build as lighting
from smallstudio_pipeline.project.blender import nodes
from smallstudio_pipeline.shots.blender import layout


@pytest.fixture
def animated(project):
    """010_010 with two shots, hero in 0010: layout and animation both published."""
    publish_model(project)
    make_cut()
    bpy.ops.pipeline.add_shot()
    layout.master_scene().frame_current = 1000
    bpy.ops.pipeline.add_shot()
    place(project, bpy.data.scenes["010_010_0010"], "hero")
    publish_cut()
    assert new_file("anim", "ANIMATION") == {"FINISHED"}
    publish_cut()
    return project.sequence("010_010")


def test_lighting_builds_a_lighting_and_comp_scene_per_shot(project, animated):
    assert new_file("light", "LIGHTING") == {"FINISHED"}
    master = layout.master_scene()
    assert layout.cut_task() == "light"
    strips = layout.shot_strips(master)
    assert [layout.strip_shot(s) for s in strips] == ["010_010_0010", "010_010_0020"]
    assert [(s.left_handle, s.right_handle - 1) for s in strips] == [(1, 48), (49, 96)]

    scene = bpy.data.scenes["010_010_0010"]
    shot = nodes.shot_node(scene)
    assert shot is not None and (shot.root.name, shot.task) == ("010_010_0010.light", "light")
    (animation,) = shot.root.children
    assert animation.name == "010_010_0010.anim" and animation.library is not None  # Linked.
    assert not [c for c in bpy.data.collections if c.override_library and not c.library]
    placed = [o.instance_collection for o in animation.all_objects if o.instance_collection]
    assert [c.name for c in placed] == ["hero"]  # Placed in layout, through animation.
    assert scene.camera is not None and scene.camera.library is not None
    assert (scene.frame_start, scene.frame_end) == (101, 148)

    rig = bpy.data.collections["010_010.lightrig"]
    world = bpy.data.worlds["010_010.world"]
    for code in ("010_010_0010", "010_010_0020"):  # Shared by every shot.
        lit = bpy.data.scenes[code]
        assert rig in lit.collection.children[:] and lit.world == world

    comp = bpy.data.scenes["010_010_0010.comp"]
    assert not comp.objects and comp.camera is None and comp.render.use_compositing
    tree = comp.compositor_effects.active.node_group  # pyright: ignore[reportAttributeAccessIssue]
    assert tree is not None
    grade = next(n for n in tree.nodes if n.bl_idname == "CompositorNodeGroup")
    assert grade.node_tree == bpy.data.node_groups["010_010.comp"]  # pyright: ignore[reportAttributeAccessIssue]
    assert (comp.frame_start, comp.frame_end) == (101, 148)


def test_lighting_needs_an_animation_publish(project):
    publish_model(project)
    make_cut()
    bpy.ops.pipeline.add_shot()
    publish_cut()
    with pytest.raises(RuntimeError, match="has no animation publish"):
        new_file("light", "LIGHTING")


def test_lighting_doesnt_publish_or_add_shots(project, animated):
    new_file("light", "LIGHTING")
    assert not bpy.ops.pipeline.add_shot.poll()
    with pytest.raises(RuntimeError, match="Light doesn't publish: render it instead"):
        publish_cut()


def test_lighting_scenes_start_with_cycles_multilayer_exrs_and_the_passes(project, animated):
    new_file("light", "LIGHTING")
    scene = bpy.data.scenes["010_010_0010"]
    image = scene.render.image_settings
    assert scene.render.engine == "CYCLES"
    assert (image.file_format, image.color_depth) == ("OPEN_EXR_MULTILAYER", "16")
    view_layer = scene.view_layers[0]
    assert all(getattr(view_layer, name) for name in lighting.PASSES)
    comp = bpy.data.scenes["010_010_0010.comp"].render.image_settings
    assert (comp.file_format, comp.color_depth) == ("OPEN_EXR", "16")


def test_renders_go_to_each_shots_folder_for_the_workfiles_version(project, animated):
    new_file("light", "LIGHTING")
    folder = project.root / "shots/010_010_0010/light/render"
    lit, comp = bpy.data.scenes["010_010_0010"], bpy.data.scenes["010_010_0010.comp"]
    assert lit.render.filepath == str(folder / "v001/010_010_0010_light_v001_")
    assert comp.render.filepath == str(folder / "v001/comp/010_010_0010_comp_v001_")
    bpy.ops.pipeline.version_up()
    assert lit.render.filepath == str(folder / "v002/010_010_0010_light_v002_")


def test_comp_reads_the_lighting_renders_once_they_exist(project, animated):
    new_file("light", "LIGHTING")
    lit, comp = bpy.data.scenes["010_010_0010"], bpy.data.scenes["010_010_0010.comp"]
    for scene in (lit, comp):  # One small frame is enough.
        scene.frame_end = scene.frame_start
        scene.render.resolution_percentage = 2
    lit.cycles.samples = 1  # pyright: ignore[reportAttributeAccessIssue]
    tree = comp.compositor_effects.active.node_group  # pyright: ignore[reportAttributeAccessIssue]
    reader = tree.nodes["renders"]
    assert reader.image is None  # Nothing rendered yet.

    bpy.ops.render.render(animation=True, scene=lit.name)
    bpy.ops.render.render(animation=True, scene=comp.name)  # Connects first.
    assert reader.image is not None and reader.image.source == "SEQUENCE"
    assert [link.from_socket.name for link in tree.links if link.from_node == reader] == [
        "Combined"
    ]
    assert (reader.frame_start, reader.frame_offset) == (101, 100)
    written = project.root / "shots/010_010_0010/light/render/v001/comp"
    assert [p.name for p in written.iterdir()] == ["010_010_0010_comp_v001_0101.exr"]


def relayout(project, sequence):
    """In layout: 0010 loses 8 frames, 0020 is omitted, 0015 is added; then publish."""
    bpy.ops.wm.open_mainfile(filepath=str(sequence.workfile_path("layout", 1)))
    master = layout.master_scene()
    first, second = layout.shot_strips(master)
    first.right_handle_offset = 8
    layout.omit_shot(second, sequence, master)
    master.frame_current = 1000
    layout.add_shot(sequence, master, master.frame_current)
    publish_cut()


def test_check_updates_brings_the_lighting_cut_in_line(project, animated):
    new_file("light", "LIGHTING")
    bpy.ops.wm.save_mainfile()
    relayout(project, animated)
    bpy.ops.wm.open_mainfile(filepath=str(animated.workfile_path("anim", 1)))
    bpy.ops.pipeline.check_updates()
    publish_cut()  # Animation now has 0015 too.

    bpy.ops.wm.open_mainfile(filepath=str(animated.workfile_path("light", 1)))
    assert bpy.ops.pipeline.check_updates() == {"FINISHED"}
    strips = layout.shot_strips(layout.master_scene())
    assert [layout.strip_shot(s) for s in strips] == ["010_010_0010", "010_010_0015"]
    assert [(s.left_handle, s.right_handle - 1) for s in strips] == [(1, 40), (41, 88)]
    for name in ("010_010_0010", "010_010_0010.comp"):
        scene = bpy.data.scenes[name]
        assert (scene.frame_start, scene.frame_end) == (101, 140)
    assert "010_010_0020" in bpy.data.scenes  # Omitted: its strip goes, its scenes stay.
    new = bpy.data.scenes["010_010_0015"]
    assert new.render.filepath.endswith("010_010_0015_light_v001_")
    assert bpy.data.scenes["010_010_0015.comp"].render.filepath.endswith("_comp_v001_")
    assert bpy.data.collections["010_010.lightrig"] in new.collection.children[:]
    assert len([c for c in bpy.data.collections if c.name.startswith("010_010.lightrig")]) == 1


def test_lighting_waits_for_animation_to_catch_up(project, animated):
    new_file("light", "LIGHTING")
    bpy.ops.wm.save_mainfile()
    relayout(project, animated)  # Animation isn't published again: it has no 0015.

    bpy.ops.wm.open_mainfile(filepath=str(animated.workfile_path("light", 1)))
    with pytest.raises(RuntimeError, match="has no animation for shot 010_010_0015"):
        bpy.ops.pipeline.check_updates()
    strips = layout.shot_strips(layout.master_scene())  # The cut is as it was.
    assert [layout.strip_shot(s) for s in strips] == ["010_010_0010", "010_010_0020"]
    assert "010_010_0015" not in bpy.data.scenes
