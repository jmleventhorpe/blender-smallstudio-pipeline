"""Runs inside Blender (see run.py): Open and Version Up."""

from pathlib import Path

import bpy
import pytest
from conftest import add_object, save_blend

from smallstudio_pipeline.blender import state


@pytest.fixture
def hero_versions(project):
    """hero's modeling v001 and v002, each with an object naming its version."""
    hero = project.create_asset("character", "hero")
    for version in (1, 2):
        bpy.ops.wm.read_homefile(use_empty=True)
        add_object(f"made_in_v{version}")
        save_blend(hero.workfile_path("modeling", version))
    bpy.ops.wm.read_homefile(use_empty=True)
    return hero


def test_open_defaults_to_the_latest_version(project, hero_versions):
    bpy.ops.pipeline.open(kind="character", entity="hero", task="modeling")
    assert Path(bpy.data.filepath) == hero_versions.workfile_path("modeling", 2)
    assert "made_in_v2" in bpy.data.objects


def test_open_a_chosen_version(project, hero_versions):
    bpy.ops.pipeline.open(kind="character", entity="hero", task="modeling", version="1")
    assert "made_in_v1" in bpy.data.objects


def test_open_only_offers_tasks_with_workfiles(project, hero_versions):
    with pytest.raises(TypeError, match="rigging"):
        bpy.ops.pipeline.open(kind="character", entity="hero", task="rigging")


def test_version_up_saves_the_next_free_version(project, hero_versions):
    bpy.ops.wm.open_mainfile(filepath=str(hero_versions.workfile_path("modeling", 1)))
    save_blend(hero_versions.workfile_path("modeling", 5))  # Someone else saved v005.
    bpy.ops.wm.open_mainfile(filepath=str(hero_versions.workfile_path("modeling", 1)))
    state.refresh()

    bpy.ops.pipeline.version_up()

    assert Path(bpy.data.filepath) == hero_versions.workfile_path("modeling", 6)
    assert state.current.label == "hero · modeling · v006"


def test_version_up_needs_a_workfile(project, hero_versions):
    save_blend(hero_versions.hero_path("modeling"))
    state.refresh()
    with pytest.raises(RuntimeError, match="Open a pipeline workfile"):
        bpy.ops.pipeline.version_up()
