from pathlib import Path
from typing import Any

import bmesh
import bpy
import pytest

import smallstudio_pipeline
from smallstudio_pipeline.blender import state
from smallstudio_pipeline.blender.identity import create_root_collection
from smallstudio_pipeline.core.entities import Project


@pytest.fixture
def registered():
    """The add-on registered for one test, starting from an empty file."""
    asset_libraries = bpy.context.preferences.filepaths.asset_libraries
    before = set(asset_libraries)
    smallstudio_pipeline.register()
    bpy.ops.wm.read_homefile(use_empty=True)
    yield
    smallstudio_pipeline.unregister()
    # Opening a project's files registers its asset library; drop the test projects'.
    for library in [lib for lib in asset_libraries if lib not in before]:
        asset_libraries.remove(library)


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


def library_load(path: Path, link: bool = False, assets_only: bool = False) -> Any:
    """bpy.data.libraries.load, which the stubs wrongly say returns None."""
    return bpy.data.libraries.load(str(path), link=link, assets_only=assets_only)


def assets_in(path: Path) -> list[str]:
    """The collections marked as assets in a .blend file."""
    with library_load(path, assets_only=True) as (data_from, _):
        return list(data_from.collections)


def link_collection(path: Path, name: str) -> bpy.types.Collection:
    with library_load(path, link=True) as (_, data_to):
        data_to.collections = [name]
    return next(c for c in bpy.data.collections if c.name == name and c.library)


def give_material(obj, name, colour):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = colour
    obj.data.materials.clear()
    obj.data.materials.append(material)


def publish_model(project, colour=(1, 0, 0, 1)):
    """hero's model: a body with a 'skin' material, published."""
    bpy.ops.wm.read_homefile(use_empty=True)
    hero = project.asset("hero") if project.assets() else project.create_asset("character", "hero")
    root = create_root_collection(hero, bpy.context.scene)
    give_material(add_cube(root, "body"), "skin", colour)
    version = hero.next_workfile_version("model")
    save_blend(hero.workfile_path("model", version))
    state.refresh()
    bpy.ops.pipeline.publish()
    return hero
