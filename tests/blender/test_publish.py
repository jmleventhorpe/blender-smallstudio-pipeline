"""Runs inside Blender (see run.py): Publish."""

import bpy
import pytest
from conftest import add_cube, assets_in, link_collection, save_blend

from smallstudio_pipeline.blender import results, state
from smallstudio_pipeline.blender.identity import create_root_collection
from smallstudio_pipeline.core.catalogs import read_catalogs
from smallstudio_pipeline.core.publishing import hero_record, read_record, record_path


def open_workfile(project, asset_type, name, task="model", objects=("body",)):
    """A saved workfile for a new asset, with its root collection holding some cubes."""
    asset = project.create_asset(asset_type, name)
    root = create_root_collection(asset, bpy.context.scene)
    for object_name in objects:
        add_cube(root, object_name)
    save_blend(asset.workfile_path(task, 1))
    state.refresh()
    return asset, root


def test_publish_writes_the_hero_the_version_and_their_records(project):
    hero, root = open_workfile(project, "character", "hero", objects=["body", "eyes"])

    bpy.ops.pipeline.publish()

    hero_file, versioned = hero.hero_path("model"), hero.publish_path("model", 1)
    assert assets_in(hero_file) == ["hero"]
    assert assets_in(versioned) == []  # Only the hero shows in the Asset Browser.
    assert root.asset_data is None  # The artist's file is left unmarked.

    record = read_record(record_path(versioned))
    assert record == hero_record(hero, "model")
    assert (record.version, record.object_names) == (1, ["body", "eyes"])
    assert record.source == "assets/character/hero/model/work/hero_model_v001.blend"
    assert record.checks["AssetRoot"] == "passed"
    assert results.last is not None and results.last.published == "hero_model v001"


def test_the_hero_links_with_a_thumbnail_in_its_type_catalog(project):
    hero, _ = open_workfile(project, "character", "hero")
    bpy.ops.pipeline.publish()

    bpy.ops.wm.read_homefile(use_empty=True)
    linked = link_collection(hero.hero_path("model"), "hero")
    assert linked.asset_data.preferred_import_method == "LINK"
    assert linked.preview is not None
    assert linked.preview.image_size[0] > 0  # pyright: ignore[reportIndexIssue]
    catalogs = {c.path: str(c.id) for c in read_catalogs(project.root / "assets")}
    assert linked.asset_data.catalog_id == catalogs["character"]


def test_publishing_again_makes_v002_and_updates_the_hero(project):
    hero, _ = open_workfile(project, "character", "hero")
    bpy.ops.pipeline.publish()
    bpy.ops.pipeline.publish()
    assert hero.publish_versions("model") == [1, 2]
    record = hero_record(hero, "model")
    assert record is not None and record.version == 2


def test_a_kit_marks_each_piece(project):
    kit, root = open_workfile(project, "lib", "street_kit", objects=[])
    for piece in ("rock", "crate"):
        collection = bpy.data.collections.new(piece)
        root.children.link(collection)
        add_cube(collection, f"{piece}_geo")
    bpy.ops.pipeline.publish()
    assert sorted(assets_in(kit.hero_path("model"))) == ["crate", "rock"]
    catalogs = [c.path for c in read_catalogs(project.root / "assets")]
    assert "lib/street_kit" in catalogs


def test_a_failing_check_blocks_the_publish_and_writes_nothing(project):
    hero, _ = open_workfile(project, "character", "hero", objects=["body.001"])
    with pytest.raises(RuntimeError, match="Publish blocked"):
        bpy.ops.pipeline.publish()
    assert hero.publish_versions("model") == []
    assert not hero.hero_path("model").exists()
    assert results.last is not None and results.last.published is None
    failed = results.last.report.get("NoNumberEndings")
    assert failed is not None and failed.status == "failed"


def test_select_fix_and_publish_again(project):
    hero, root = open_workfile(project, "character", "hero", objects=["body", "eyes.001"])
    root.name = "hero_copy"
    with pytest.raises(RuntimeError, match="Publish blocked"):
        bpy.ops.pipeline.publish()

    bpy.ops.pipeline.select_issue(check_id="NoNumberEndings", index=0)
    assert [obj.name for obj in bpy.context.selected_objects] == ["eyes.001"]
    bpy.ops.pipeline.fix_check(check_id="AssetRoot")  # Renames the root.
    assert root.name == "hero"

    eyes = bpy.data.objects["eyes.001"]
    eyes.name = eyes.data.name = "eyes"  # The artist fixes the rest by hand.
    bpy.ops.pipeline.publish()
    assert hero.publish_versions("model") == [1]


def test_publish_needs_a_workfile(project):
    hero, _ = open_workfile(project, "character", "hero")
    bpy.ops.pipeline.publish()
    bpy.ops.wm.open_mainfile(filepath=str(hero.hero_path("model")))
    with pytest.raises(RuntimeError, match="Open a pipeline workfile to publish"):
        bpy.ops.pipeline.publish()
