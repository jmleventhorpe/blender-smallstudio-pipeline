"""Runs inside Blender (see run.py): building a sequence's lighting file."""

import bpy
import pytest
from conftest import make_cut, place, publish_model

from smallstudio_pipeline.lighting.blender import build as lighting
from smallstudio_pipeline.project.blender import nodes
from smallstudio_pipeline.shots.blender import layout


def publish_cut():
    """Publish the open cut file, from its sequence node."""
    master = layout.master_scene()
    nodes.make_active(master, nodes.sequence_node(master).root)  # pyright: ignore[reportOptionalMemberAccess]
    assert bpy.ops.pipeline.publish() == {"FINISHED"}


def new_file(task, kind):
    """An empty file saved as 010_010's workfile for a task, built with New Node."""
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.pipeline.save_to(category="sequence", entity="010_010", task=task)
    return bpy.ops.pipeline.new_node(kind=kind, sequence="010_010")


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
