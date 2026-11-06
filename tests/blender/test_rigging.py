"""Runs inside Blender (see run.py): a rig node takes its model's latest materials."""

from pathlib import Path

import bpy
from conftest import add_cube, give_material, publish_model, save_blend

from smallstudio_pipeline.project.blender.identity import TASK, create_root_collection
from smallstudio_pipeline.publishing.core.publishing import hero_record


def rig_workfile(hero):
    """hero's rig workfile: a rig node holding a body (as the model's) and a rig-only part."""
    bpy.ops.wm.read_homefile(use_empty=True)
    root = create_root_collection(hero, bpy.context.scene, "rig")
    give_material(add_cube(root, "body"), "skin", (0.5, 0.5, 0.5, 1))
    give_material(add_cube(root, "rig_only"), "plastic", (0, 0, 1, 1))
    save_blend(hero.workfile_path("rig", 1))
    return root


def test_a_rig_node_is_made_empty_for_its_task(project):
    hero = project.create_asset("character", "hero")
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.pipeline.new_node(kind="ASSET", asset="hero", task="rig")
    root = bpy.data.collections["hero"]
    assert root[TASK] == "rig" and not root.all_objects
    assert hero.workfile_versions("rig") == []  # Making a node saves nothing.


def test_rig_publishes_take_the_models_latest_materials(project):
    hero = publish_model(project, colour=(1, 0, 0, 1))
    rig_workfile(hero)
    path = Path(bpy.data.filepath)

    publish_model(project, colour=(0, 1, 0, 1))  # The model's skin turns green: v002.
    bpy.ops.wm.open_mainfile(filepath=str(path))
    bpy.ops.pipeline.publish()
    bpy.ops.pipeline.publish()  # Twice, to be sure copies don't pile up.

    body = bpy.data.objects["body"]
    colour = body.material_slots[0].material.diffuse_color
    assert list(colour[:]) == [0, 1, 0, 1]  # pyright: ignore[reportIndexIssue]
    assert sorted(m.name for m in bpy.data.materials) == ["plastic", "skin"]
    record = hero_record(hero, "rig")
    assert (
        record is not None and record.source == "assets/character/hero/rig/work/hero_rig_v001.blend"
    )


def test_a_rig_publishes_without_a_model_publish(project):
    hero = project.create_asset("character", "hero")
    rig_workfile(hero)
    assert bpy.ops.pipeline.publish() == {"FINISHED"}
    assert hero.latest_publish_version("rig") == 1
