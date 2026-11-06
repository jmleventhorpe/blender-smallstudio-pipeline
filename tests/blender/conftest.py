from pathlib import Path
from typing import Any

import bmesh
import bpy
import pytest

import smallstudio_pipeline
from smallstudio_pipeline.project.blender.identity import create_root_collection
from smallstudio_pipeline.project.core.machine import ENV
from smallstudio_pipeline.project.core.project import Project
from smallstudio_pipeline.session import state


@pytest.fixture(autouse=True)
def machine_settings(tmp_path: Path, monkeypatch) -> Path:
    """This machine's settings file, in the test's own folder, never the real one."""
    path = tmp_path / "machine" / "projects.json"
    monkeypatch.setenv(ENV, str(path))
    return path


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
    from smallstudio_pipeline.workfiles.blender import workfiles

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


def publish_prop(project, name):
    """A prop's model, published: one cube in its root."""
    bpy.ops.wm.read_homefile(use_empty=True)
    asset = project.create_asset("prop", name)
    add_cube(create_root_collection(asset, bpy.context.scene), f"{name}_box")
    save_blend(asset.workfile_path("model", 1))
    state.refresh()
    bpy.ops.pipeline.publish()
    return asset


def place(project, scene, asset_name, location=(0.0, 0.0, 0.0)):
    """Place a linked asset in a scene with an empty, as dragging it from the Asset Browser does."""
    asset = project.asset(asset_name)
    linked = link_collection(asset.hero_path("model"), asset_name)
    empty = bpy.data.objects.new(asset_name, None)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = linked
    empty.location = location
    # Into the active collection, as dragging does: a shot's node, in a shot's scene.
    scene.view_layers[0].active_layer_collection.collection.objects.link(empty)
    return empty


def placed_at(obj):
    """Where an object stands, from its own transform up its parents (spike T13)."""
    matrix = obj.matrix_basis.copy()
    while obj.parent is not None:
        matrix = obj.parent.matrix_basis @ obj.matrix_parent_inverse @ matrix
        obj = obj.parent
    return tuple(round(value, 4) for value in matrix.translation)


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
