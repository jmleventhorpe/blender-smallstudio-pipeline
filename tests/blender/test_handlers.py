"""Runs inside Blender (see run.py): the menu, the state handlers and in-use markers."""

import json
from datetime import UTC, datetime

import bpy
from conftest import save_blend

import smallstudio_pipeline
from smallstudio_pipeline.blender import menu, state
from smallstudio_pipeline.core.inuse import marker_path, read_marker


def test_saving_a_workfile_marks_it_in_use_and_versioning_up_moves_the_mark(project):
    hero = project.create_asset("character", "hero")
    first = hero.workfile_path("modeling", 1)
    save_blend(first)
    marker = read_marker(first)
    assert marker is not None and marker.is_mine()

    bpy.ops.pipeline.version_up()
    assert not marker_path(first).exists()
    assert read_marker(hero.workfile_path("modeling", 2)) is not None


def test_opening_another_file_releases_the_mark(project):
    hero = project.create_asset("character", "hero")
    first, second = hero.workfile_path("modeling", 1), hero.workfile_path("modeling", 2)
    save_blend(first)
    save_blend(second)
    bpy.ops.wm.open_mainfile(filepath=str(first))
    assert read_marker(first) is not None
    assert not marker_path(second).exists()


def test_someone_elses_mark_is_kept_and_warned_about(project):
    hero = project.create_asset("character", "hero")
    path = hero.workfile_path("modeling", 1)
    save_blend(path)
    bpy.ops.wm.read_homefile(use_empty=True)  # Close it, releasing our mark.
    opened = datetime.now(UTC).isoformat()
    other = {"user": "sam", "machine": "pc-02", "pid": 4242, "opened": opened}
    marker_path(path).write_text(json.dumps(other))

    bpy.ops.wm.open_mainfile(filepath=str(path))

    assert state.current.warning is not None and "sam has this file open on pc-02" in (
        state.current.warning
    )
    marker = read_marker(path)
    assert marker is not None and marker.machine == "pc-02"


def test_publishes_are_not_marked_and_warn(project):
    hero = project.create_asset("character", "hero")
    publish = hero.hero_path("modeling")
    save_blend(publish)
    bpy.ops.wm.open_mainfile(filepath=str(publish))
    assert not marker_path(publish).exists()
    assert state.current.warning == state.PUBLISH


def test_unregistering_releases_the_mark_and_removes_the_menu(project):
    hero = project.create_asset("character", "hero")
    path = hero.workfile_path("modeling", 1)
    save_blend(path)
    top_bar = bpy.types.TOPBAR_MT_editor_menus
    assert menu.draw_in_top_bar in top_bar._dyn_ui_initialize()

    smallstudio_pipeline.unregister()

    assert not marker_path(path).exists()
    assert menu.draw_in_top_bar not in top_bar._dyn_ui_initialize()
    assert not hasattr(bpy.types, "PIPELINE_MT_main")
    smallstudio_pipeline.register()  # The fixture unregisters again afterwards.
