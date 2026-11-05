"""Runs inside Blender (see run.py): what the top bar says about the open file."""

from pathlib import Path

import bpy
import pytest

from smallstudio_pipeline.project.core.machine import MachineSettings, ProjectFolder, save_settings
from smallstudio_pipeline.project.core.project import Project
from smallstudio_pipeline.session import state


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project.create(tmp_path / "show")


def test_a_workfile(project):
    hero = project.create_asset("character", "hero")
    current = state.describe(str(hero.workfile_path("rig", 3)), None)
    assert current.label == "hero · rig · v003"
    assert current.warnings == []


def test_a_publish_warns(project):
    hero = project.create_asset("character", "hero")
    current = state.describe(str(hero.hero_path("rig")), None)
    assert current.label == "hero · rig · published"
    assert current.warnings == [state.PUBLISH]


def test_an_unmanaged_file_in_the_project_warns(project):
    current = state.describe(str(project.root / "scratch.blend"), None)
    assert current.label == "show · not a pipeline file"
    assert current.warnings == [state.UNMANAGED]


def test_an_unsaved_file_uses_the_active_project(project):
    assert state.describe("", project.root).label == "show · unsaved file"
    assert state.describe("", None).label == "No project"


def test_a_broken_config_is_shown_not_raised(project):
    (project.root / "pipeline.toml").write_text("[project\n")
    current = state.describe(str(project.root / "scratch.blend"), None)
    assert current.label == "Project error"
    assert len(current.warnings) == 1 and "isn't valid TOML" in current.warnings[0]


def test_refresh_reads_the_open_file(project):
    hero = project.create_asset("character", "hero")
    path = hero.workfile_path("model", 1)
    path.parent.mkdir(parents=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    state.refresh()
    assert state.current.label == "hero · model · v001"


def test_the_active_project_comes_from_this_machines_settings_file(project, machine_settings):
    save_settings(MachineSettings([ProjectFolder("show", str(project.root))]), machine_settings)
    bpy.ops.wm.read_homefile(use_empty=True)
    state.refresh()
    assert state.current.project is not None and state.current.project.root == project.root
    assert state.current.label == "show · unsaved file"
