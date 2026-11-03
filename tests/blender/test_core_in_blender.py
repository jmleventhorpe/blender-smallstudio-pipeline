"""Runs inside Blender (see run.py): the core works with Blender's own Python."""

from pathlib import Path

from smallstudio_pipeline.core.context import file_context
from smallstudio_pipeline.core.entities import Project


def test_core_builds_a_project_in_blender(tmp_path: Path):
    project = Project.create(tmp_path / "show")
    hero = project.create_asset("character", "hero")
    shot = project.create_sequence("010").create_shot()
    context = file_context(project, hero.workfile_path("rig", 1))
    assert context is not None and context.label == "hero · rig · v001"
    assert shot.render_path("light", 1).name == "v001"
