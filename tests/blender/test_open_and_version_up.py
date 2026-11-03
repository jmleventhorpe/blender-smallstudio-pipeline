"""Runs inside Blender (see run.py): Open and Version Up."""

from pathlib import Path

import bpy
import pytest
from conftest import add_object, save_blend

from smallstudio_pipeline.blender import state


@pytest.fixture
def hero_versions(project):
    """hero's model v001 and v002, each with an object naming its version."""
    hero = project.create_asset("character", "hero")
    for version in (1, 2):
        bpy.ops.wm.read_homefile(use_empty=True)
        add_object(f"made_in_v{version}")
        save_blend(hero.workfile_path("model", version))
    bpy.ops.wm.read_homefile(use_empty=True)
    return hero


def test_open_defaults_to_the_latest_version(project, hero_versions):
    bpy.ops.pipeline.open(kind="character", entity="hero", task="model")
    assert Path(bpy.data.filepath) == hero_versions.workfile_path("model", 2)
    assert "made_in_v2" in bpy.data.objects


def test_open_a_chosen_version(project, hero_versions):
    bpy.ops.pipeline.open(kind="character", entity="hero", task="model", version="1")
    assert "made_in_v1" in bpy.data.objects


def test_open_only_offers_tasks_with_workfiles(project, hero_versions):
    with pytest.raises(TypeError, match="rig"):
        bpy.ops.pipeline.open(kind="character", entity="hero", task="rig")


def test_version_up_saves_the_next_free_version(project, hero_versions):
    bpy.ops.wm.open_mainfile(filepath=str(hero_versions.workfile_path("model", 1)))
    save_blend(hero_versions.workfile_path("model", 5))  # Someone else saved v005.
    bpy.ops.wm.open_mainfile(filepath=str(hero_versions.workfile_path("model", 1)))
    state.refresh()

    bpy.ops.pipeline.version_up()

    assert Path(bpy.data.filepath) == hero_versions.workfile_path("model", 6)
    assert state.current.label == "hero · model · v006"


def test_version_up_needs_a_workfile(project, hero_versions):
    save_blend(hero_versions.hero_path("model"))
    state.refresh()
    with pytest.raises(RuntimeError, match="Open a pipeline workfile"):
        bpy.ops.pipeline.version_up()
