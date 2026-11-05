"""Runs inside Blender (see run.py): the asset library, Check Updates and stale builds."""

import json
from datetime import UTC, datetime
from pathlib import Path

import bpy
import pytest
from conftest import add_cube, link_collection, publish_model, save_blend

from smallstudio_pipeline.common.errors import PipelineError
from smallstudio_pipeline.loading.blender import libraries, updates
from smallstudio_pipeline.publishing.core.publishing import new_record, plan_publish, write_records
from smallstudio_pipeline.session import state
from smallstudio_pipeline.workfiles.core.inuse import marker_path


def test_the_projects_assets_become_an_asset_library_once(project):
    assert libraries.register_asset_library(project)
    assert not libraries.register_asset_library(project)
    folder = (project.root / "assets").resolve()
    added = [
        lib
        for lib in bpy.context.preferences.filepaths.asset_libraries
        if Path(bpy.path.abspath(lib.path)).resolve() == folder
    ]
    assert len(added) == 1
    assert added[0].name == "show" and added[0].import_method == "LINK"


def republish_behind_the_files_back(hero, extra_object):
    """Publish hero's model again without leaving the open file, as another artist would."""
    root = bpy.data.collections.new("hero")  # A local "hero", beside the linked one.
    add_cube(root, "body")
    add_cube(root, extra_object)
    plan = plan_publish(hero, "model")
    bpy.data.libraries.write(str(plan.hero), {root}, path_remap="RELATIVE_ALL")
    write_records(plan, new_record(plan, hero.workfile_path("model", 1), "5.2.2", ["body"]))
    bpy.data.collections.remove(root)


HERO_MODEL = "assets/character/hero/model/publish/hero_model.blend"


def open_layout(project, hero, linking_hero=True):
    """Open sequence 010's layout file, linking hero's model unless told not to."""
    sequence = project.create_sequence("010")
    bpy.ops.wm.read_homefile(use_empty=True)
    if linking_hero:
        linked = link_collection(hero.hero_path("model"), "hero")
        bpy.context.scene.collection.children.link(linked)
    save_blend(sequence.workfile_path("layout", 1))
    bpy.ops.wm.open_mainfile(filepath=str(sequence.workfile_path("layout", 1)))


def linked_hero_objects():
    hero = next(c for c in bpy.data.collections if c.name == "hero" and c.library)
    return [obj.name for obj in hero.all_objects]


def test_check_updates_reloads_what_was_published_again(project):
    hero = publish_model(project)
    open_layout(project, hero)
    assert updates.seen == {HERO_MODEL: 1}

    republish_behind_the_files_back(hero, "new_hat")
    bpy.ops.pipeline.check_updates()

    assert "new_hat" in linked_hero_objects()
    assert updates.seen[HERO_MODEL] == 2
    bpy.ops.pipeline.check_updates()  # Nothing new the second time.


def test_check_updates_covers_assets_linked_since_the_file_opened(project):
    hero = publish_model(project)
    open_layout(project, hero, linking_hero=False)
    assert updates.seen == {}
    linked = link_collection(hero.hero_path("model"), "hero")  # From the Asset Browser.
    bpy.context.scene.collection.children.link(linked)

    republish_behind_the_files_back(hero, "new_hat")
    bpy.ops.pipeline.check_updates()

    assert "new_hat" in linked_hero_objects()
    assert updates.seen == {HERO_MODEL: 2}


def test_check_updates_skips_publishes_no_longer_linked(project):
    hero = publish_model(project)
    open_layout(project, hero)
    bpy.data.libraries.remove(libraries.linked_publishes(project)[HERO_MODEL])

    republish_behind_the_files_back(hero, "new_hat")
    assert bpy.ops.pipeline.check_updates() == {"FINISHED"}
    assert updates.seen == {}


def test_a_rig_built_from_an_older_model_is_flagged(project):
    hero = publish_model(project)
    bpy.ops.pipeline.new_workfile(category="character", entity="hero", task="rig")
    rig = Path(bpy.data.filepath)
    publish_model(project)  # Model v002.

    bpy.ops.wm.open_mainfile(filepath=str(rig))
    assert len(state.current.warnings) == 1
    assert "hero_model (v001 → v002)" in state.current.warnings[0]
    assert hero.latest_publish_version("model") == 2


def test_a_stale_build_and_someone_else_having_the_file_are_both_warned_about(project):
    publish_model(project)
    bpy.ops.pipeline.new_workfile(category="character", entity="hero", task="rig")
    rig = Path(bpy.data.filepath)
    publish_model(project)  # Model v002; also closes the rig, releasing our mark.
    opened = datetime.now(UTC).isoformat()
    other = {"user": "sam", "machine": "pc-02", "pid": 4242, "opened": opened}
    marker_path(rig).write_text(json.dumps(other))

    bpy.ops.wm.open_mainfile(filepath=str(rig))

    warnings = state.current.warnings
    assert len(warnings) == 2
    assert "sam has this file open" in warnings[0] and "hero_model" in warnings[1]


def test_an_up_to_date_rig_isnt_flagged(project):
    publish_model(project)
    bpy.ops.pipeline.new_workfile(category="character", entity="hero", task="rig")
    bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
    assert state.current.warnings == []


def test_loading_a_root_the_publish_doesnt_have_says_so(project):
    hero = publish_model(project)
    with pytest.raises(PipelineError, match=r"hero_model\.blend has no collection called villain"):
        libraries.load_root(hero.hero_path("model"), "villain", link=True)
