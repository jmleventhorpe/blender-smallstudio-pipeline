"""Runs inside Blender (see run.py): New Asset and New Workfile."""

from pathlib import Path

import bpy
import pytest
from conftest import add_object, save_blend

from smallstudio_pipeline.blender import state
from smallstudio_pipeline.blender.identity import INSTANCE_ID, asset_identity


def test_new_asset_saves_its_first_workfile_with_a_root_collection(project):
    bpy.ops.pipeline.new_asset(asset_type="character", name="hero")

    hero = project.asset("hero")
    assert Path(bpy.data.filepath) == hero.workfile_path("model", 1)
    root = bpy.data.collections["hero"]
    assert asset_identity(root) == ("hero", "character")
    assert root[INSTANCE_ID] == ""
    assert root.is_property_overridable_library(f'["{INSTANCE_ID}"]')
    assert bpy.context.scene.render.fps == 24
    render = bpy.context.scene.render
    assert (render.resolution_x, render.resolution_y) == (1920, 1080)


def test_new_asset_reports_bad_names(project):
    with pytest.raises(RuntimeError, match="isn't a valid name"):
        bpy.ops.pipeline.new_asset(asset_type="prop", name="Street Lamp")
    assert project.assets() == []


def test_new_workfile_starts_from_the_starter_file(project):
    add_object("from_the_starter")
    save_blend(project.root / "starters/layout.blend")
    (project.root / "pipeline.toml").write_text(
        '[tasks.layout]\nstarter = "starters/layout.blend"\n'
    )
    state.refresh()  # Reload the changed config.
    assert state.current.project is not None
    sequence = state.current.project.create_sequence("010")

    bpy.ops.pipeline.new_workfile(category="sequence", entity="010_010", task="layout")

    assert Path(bpy.data.filepath) == sequence.workfile_path("layout", 1)
    assert "from_the_starter" in bpy.data.objects


def test_new_workfile_refuses_a_started_task(project):
    hero = project.create_asset("character", "hero")
    save_blend(hero.workfile_path("rig", 1))
    with pytest.raises(RuntimeError, match="already has rig workfiles"):
        bpy.ops.pipeline.new_workfile(category="character", entity="hero", task="rig")


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
