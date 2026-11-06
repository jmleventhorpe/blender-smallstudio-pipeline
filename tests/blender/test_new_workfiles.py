"""Runs inside Blender (see run.py): New Workfile, Save To, and New Node with its edits."""

from pathlib import Path

import bpy
import pytest
from conftest import add_object, save_blend

from smallstudio_pipeline.project.blender import nodes
from smallstudio_pipeline.project.blender.identity import INSTANCE_ID, TASK


def test_new_workfile_only_saves_an_empty_file_in_the_right_place(project):
    hero = project.create_asset("character", "hero")
    save_blend(hero.workfile_path("model", 2))
    bpy.ops.pipeline.new_workfile(category="character", entity="hero", task="model")
    assert Path(bpy.data.filepath) == hero.workfile_path("model", 3)  # Its next free version.
    assert not bpy.data.collections and not bpy.data.objects


def test_save_to_saves_the_open_file_as_any_tasks_next_workfile(project):
    hero = project.create_asset("character", "hero")
    bpy.ops.wm.read_homefile(use_empty=True)
    add_object("sketch")
    bpy.ops.pipeline.save_to(category="character", entity="hero", task="rig")
    assert Path(bpy.data.filepath) == hero.workfile_path("rig", 1)
    assert "sketch" in bpy.data.objects


def test_new_node_makes_a_new_asset_and_its_empty_node(project):
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.pipeline.new_node(kind="ASSET", asset="NEW", asset_type="prop", name="crate")
    crate = project.asset("crate")
    (node,) = nodes.nodes_in(bpy.context.scene)
    assert (node.kind, node.name, node.asset_type, node.task) == ("asset", "crate", "prop", "model")
    assert node.root.is_property_overridable_library(f'["{INSTANCE_ID}"]')
    assert not node.root.objects and crate.workfile_versions("model") == []
    assert bpy.context.view_layer.active_layer_collection.collection == node.root


def test_new_node_adds_an_optional_task_and_nests_in_the_active_node(project):
    street = project.create_asset("set", "street")
    project.create_asset("prop", "crate")
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.pipeline.new_node(kind="ASSET", asset="street", task="model")
    bpy.ops.pipeline.new_node(kind="ASSET", asset="crate", task="rig")  # Inside the street.
    assert "rig" in project.asset("crate").tasks  # Props' rig task is optional.
    crate = bpy.data.collections["crate"]
    assert crate in bpy.data.collections[street.name].children[:] and crate[TASK] == "rig"


def test_new_node_reports_bad_names(project):
    with pytest.raises(RuntimeError, match="isn't a valid name"):
        bpy.ops.pipeline.new_node(kind="ASSET", asset="NEW", asset_type="prop", name="Bad Name")


def test_nodes_can_change_task_or_go_back_to_plain_collections(project):
    project.create_asset("character", "hero")
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.pipeline.new_node(kind="ASSET", asset="hero", task="model")
    bpy.ops.pipeline.edit_node(node="hero", asset="hero", asset_type="character", task="rig")
    assert bpy.data.collections["hero"][TASK] == "rig"
    bpy.ops.pipeline.remove_node(node="hero")
    assert nodes.nodes_in(bpy.context.scene) == [] and "hero" in bpy.data.collections


def test_unsaved_changes_are_saved_first(project, unsaved_changes):
    hero = project.create_asset("character", "hero")
    project.create_sequence("010")
    first = hero.workfile_path("model", 1)
    save_blend(first)
    add_object("unsaved_work")

    bpy.ops.pipeline.new_workfile(category="sequence", entity="010_010", task="layout")

    bpy.ops.wm.open_mainfile(filepath=str(first))
    assert "unsaved_work" in bpy.data.objects


def test_unsaved_changes_in_an_untitled_file_need_a_choice(project, unsaved_changes):
    project.create_asset("character", "hero")
    with pytest.raises(RuntimeError, match="never been saved"):
        bpy.ops.pipeline.new_workfile(category="character", entity="hero", task="model")
    bpy.ops.pipeline.new_workfile(
        category="character", entity="hero", task="model", unsaved="DISCARD"
    )
    assert bpy.data.filepath.endswith("hero_model_v001.blend")
