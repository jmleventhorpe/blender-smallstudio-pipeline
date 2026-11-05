"""Runs inside Blender (see run.py): rigs start from the model and keep its materials."""

from pathlib import Path

import bpy
import pytest
from conftest import add_cube, give_material, publish_model, save_blend

from smallstudio_pipeline.project.blender.identity import INSTANCE_ID, built_from
from smallstudio_pipeline.publishing.core.publishing import Dependency, hero_record

MODEL_HERO = "assets/character/hero/model/publish/hero_model.blend"


def test_a_rig_workfile_starts_from_the_latest_model(project):
    hero = publish_model(project)
    bpy.ops.pipeline.new_workfile(category="character", entity="hero", task="rig")

    assert Path(bpy.data.filepath) == hero.workfile_path("rig", 1)
    root = bpy.data.collections["hero"]
    assert root.library is None and "body" in root.objects  # Appended, not linked.
    assert root.asset_data is None  # The workfile's copy isn't an asset.
    assert root.is_property_overridable_library(f'["{INSTANCE_ID}"]')
    assert built_from(root) == Dependency(MODEL_HERO, 1)


def test_a_rig_needs_a_model_publish(project):
    project.create_asset("character", "hero")
    with pytest.raises(RuntimeError, match="no model publish yet"):
        bpy.ops.pipeline.new_workfile(category="character", entity="hero", task="rig")


def test_rig_publishes_take_the_models_latest_materials(project):
    hero = publish_model(project, colour=(1, 0, 0, 1))
    bpy.ops.pipeline.new_workfile(category="character", entity="hero", task="rig")
    rig_workfile = Path(bpy.data.filepath)
    give_material(add_cube(bpy.data.collections["hero"], "rig_only"), "plastic", (0, 0, 1, 1))
    save_blend(rig_workfile)

    publish_model(project, colour=(0, 1, 0, 1))  # The model's skin turns green: v002.
    bpy.ops.wm.open_mainfile(filepath=str(rig_workfile))
    bpy.ops.pipeline.publish()
    bpy.ops.pipeline.publish()  # Twice, to be sure copies don't pile up.

    body = bpy.data.objects["body"]
    colour = body.material_slots[0].material.diffuse_color
    assert list(colour[:]) == [0, 1, 0, 1]  # pyright: ignore[reportIndexIssue]
    assert sorted(m.name for m in bpy.data.materials) == ["plastic", "skin"]
    record = hero_record(hero, "rig")
    assert record is not None and record.built_from == Dependency(MODEL_HERO, 1)
