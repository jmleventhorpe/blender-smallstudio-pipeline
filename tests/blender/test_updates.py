"""Runs inside Blender (see run.py): the asset library, Check Updates and stale builds."""

from pathlib import Path

import bpy
from conftest import add_cube, link_collection, publish_model, save_blend

from smallstudio_pipeline.blender import libraries, state, updates
from smallstudio_pipeline.core.publishing import new_record, plan_publish, write_records


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


def test_check_updates_reloads_what_was_published_again(project):
    hero = publish_model(project)
    sequence = project.create_sequence("010")
    bpy.ops.wm.read_homefile(use_empty=True)
    linked = link_collection(hero.hero_path("model"), "hero")
    bpy.context.scene.collection.children.link(linked)
    save_blend(sequence.workfile_path("layout", 1))
    bpy.ops.wm.open_mainfile(filepath=str(sequence.workfile_path("layout", 1)))
    assert updates.seen == {"assets/character/hero/model/publish/hero_model.blend": 1}

    republish_behind_the_files_back(hero, "new_hat")
    bpy.ops.pipeline.check_updates()

    hero_now = next(c for c in bpy.data.collections if c.name == "hero" and c.library)
    assert "new_hat" in [obj.name for obj in hero_now.all_objects]
    assert updates.seen["assets/character/hero/model/publish/hero_model.blend"] == 2
    bpy.ops.pipeline.check_updates()  # Nothing new the second time.


def test_a_rig_built_from_an_older_model_is_flagged(project):
    hero = publish_model(project)
    bpy.ops.pipeline.new_workfile(kind="character", entity="hero", task="rig")
    rig = Path(bpy.data.filepath)
    publish_model(project)  # Model v002.

    bpy.ops.wm.open_mainfile(filepath=str(rig))
    assert state.current.warning is not None
    assert "hero_model v001 → v002" in state.current.warning
    assert hero.latest_publish_version("model") == 2


def test_an_up_to_date_rig_isnt_flagged(project):
    publish_model(project)
    bpy.ops.pipeline.new_workfile(kind="character", entity="hero", task="rig")
    bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
    assert state.current.warning is None
