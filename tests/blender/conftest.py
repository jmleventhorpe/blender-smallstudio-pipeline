from pathlib import Path

import bpy
import pytest

import smallstudio_pipeline
from smallstudio_pipeline.blender import state
from smallstudio_pipeline.core.entities import Project


@pytest.fixture
def registered():
    """The add-on registered for one test, starting from an empty file."""
    smallstudio_pipeline.register()
    bpy.ops.wm.read_homefile(use_empty=True)
    yield
    smallstudio_pipeline.unregister()


@pytest.fixture
def project(tmp_path: Path, registered) -> Project:
    """A new project, made the active one as the preferences would."""
    project = Project.create(tmp_path / "show")
    state.current = state.describe("", project.root)
    return project


@pytest.fixture
def unsaved_changes(monkeypatch):
    """Make the open file count as changed. Python edits don't set the flag in background."""
    from smallstudio_pipeline.blender import workfiles

    monkeypatch.setattr(workfiles, "has_unsaved_changes", lambda: True)


def add_object(name: str) -> None:
    bpy.context.scene.collection.objects.link(bpy.data.objects.new(name, None))


def save_blend(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
