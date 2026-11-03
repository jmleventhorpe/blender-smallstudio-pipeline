from pathlib import Path

import bmesh
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
def project(tmp_path: Path, registered, monkeypatch) -> Project:
    """A new project, set as the active one in the preferences."""
    project = Project.create(tmp_path / "show")
    monkeypatch.setattr(state, "active_project_root", lambda: project.root)
    state.refresh()
    return project


@pytest.fixture
def unsaved_changes(monkeypatch):
    """Make the open file count as changed. Python edits don't set the flag in background."""
    from smallstudio_pipeline.blender import workfiles

    monkeypatch.setattr(workfiles, "has_unsaved_changes", lambda: True)


def add_object(name: str) -> None:
    bpy.context.scene.collection.objects.link(bpy.data.objects.new(name, None))


def add_cube(collection: bpy.types.Collection, name: str) -> bpy.types.Object:
    """A cube mesh object in a collection, its data named after it."""
    mesh = bpy.data.meshes.new(name)
    cube = bmesh.new()
    bmesh.ops.create_cube(cube, size=1.0)
    cube.to_mesh(mesh)
    cube.free()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def save_blend(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
