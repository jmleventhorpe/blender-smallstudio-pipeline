"""Runs inside Blender (see run.py): the core works with Blender's own Python."""

from pathlib import Path

from smallstudio_pipeline.project.core.project import Project
from smallstudio_pipeline.workfiles.core.context import file_context


def test_core_builds_a_project_in_blender(tmp_path: Path):
    project = Project.create(tmp_path / "show")
    hero = project.create_asset("character", "hero")
    shot = project.create_sequence("010").create_shot()
    context = file_context(project, hero.workfile_path("rig", 1))
    assert context is not None and context.label == "hero · rig · v001"
    assert shot.render_path("light", 1).name == "v001"


def test_the_bundled_validator_runs_in_blender():
    from importlib.metadata import version

    from publish_validator.hosts.blender import BlenderHost

    assert version("publish-validator") == "0.2.0"
    assert BlenderHost.name == "blender"
