from pathlib import Path

import pytest

from smallstudio_pipeline.core.catalogs import CATALOG_FILE, ensure_catalog, read_catalogs
from smallstudio_pipeline.core.config import load_config
from smallstudio_pipeline.core.context import file_context
from smallstudio_pipeline.core.errors import ConfigError, EntityNotFound, PipelineError
from smallstudio_pipeline.core.publishing import (
    Dependency,
    built_from,
    hero_record,
    new_record,
    plan_publish,
    publish_target,
    read_record,
    removed_objects,
    write_records,
)
from smallstudio_pipeline.core.updates import Change, changed, stale_build


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def publish(entity, task, names=("body",), built=None):
    """Write a publish's files and records, as a Publish would (minus the .blend data)."""
    plan = plan_publish(entity, task)
    touch(plan.path)
    touch(plan.hero)
    source = entity.workfile_path(task, 1)
    write_records(plan, new_record(plan, source, "5.2.2", list(names), built_from=built))
    return plan


# Targets


def test_publishing_in_the_assets_own_workfile(project):
    hero = project.create_asset("character", "hero")
    target = publish_target(project, file_context(project, hero.workfile_path("rig", 3)), "hero")
    assert (target.asset, target.task, target.in_context) == (hero, "rig", False)


def test_publishing_a_prop_built_inside_a_set(project):
    street = project.create_asset("set", "street")
    crate = project.create_asset("prop", "crate", tasks=["rig"])
    in_set = file_context(project, street.workfile_path("model", 2))
    target = publish_target(project, in_set, "crate")
    assert (target.asset, target.task, target.in_context) == (crate, "model", True)


def test_publish_targets_refuse_publishes_unmanaged_files_and_unknown_assets(project):
    hero = project.create_asset("character", "hero")
    with pytest.raises(PipelineError, match="read-only"):
        publish_target(project, file_context(project, hero.hero_path("rig")), "hero")
    with pytest.raises(PipelineError, match="Save this file as a pipeline workfile"):
        publish_target(project, None, "hero")
    work = file_context(project, hero.workfile_path("rig", 1))
    with pytest.raises(EntityNotFound, match="Did you mean 'hero'"):
        publish_target(project, work, "heroo")


# Plans and records


def test_plans_count_up_and_records_sit_beside_the_files(project):
    hero = project.create_asset("character", "hero")
    first = publish(hero, "rig")
    assert first.version == 1
    assert first.record.name == "hero_rig_v001.json"
    assert first.hero_record.name == "hero_rig.json"
    second = plan_publish(hero, "rig")
    assert second.version == 2
    assert second.hero == first.hero


def test_records_round_trip_and_the_hero_record_is_the_latest(project):
    hero = project.create_asset("character", "hero")
    assert hero_record(hero, "rig") is None
    publish(hero, "rig", names=["body", "eyes"])
    plan = publish(hero, "rig", names=["body"], built=Dependency("x.blend", 3))
    record = hero_record(hero, "rig")
    assert record is not None
    assert record == read_record(plan.record)
    assert (record.version, record.object_names) == (2, ["body"])
    assert record.source == "assets/character/hero/rig/work/hero_rig_v001.blend"
    assert record.built_from == Dependency("x.blend", 3)
    assert record.tool == "0.1.0"


def test_removed_objects(project):
    hero = project.create_asset("character", "hero")
    publish(hero, "rig", names=["body", "eyes", "hair"])
    previous = hero_record(hero, "rig")
    assert removed_objects(previous, ["body", "hair_new"]) == ["eyes", "hair"]
    assert removed_objects(None, ["body"]) == []


def test_a_rig_is_built_from_the_latest_model(project):
    hero = project.create_asset("character", "hero")
    with pytest.raises(PipelineError, match="no model publish yet"):
        built_from(hero, "rig")
    publish(hero, "model")
    publish(hero, "model")
    assert built_from(hero, "rig") == Dependency(
        "assets/character/hero/model/publish/hero_model.blend", 2
    )
    assert built_from(hero, "model") is None  # model builds on nothing.


def test_builds_on_must_name_a_publishing_task_of_the_same_entity(make_project):
    with pytest.raises(ConfigError, match="'layout' isn't a publishing asset task"):
        make_project('[tasks.rig]\nbuilds_on = "layout"\n')


# Updates


def test_changed_publishes_and_stale_builds(project):
    hero = project.create_asset("character", "hero")
    publish(hero, "model")
    hero_model = "assets/character/hero/model/publish/hero_model.blend"
    seen = {hero_model: 1, "assets/lib/kit/model/publish/kit_model.blend": None}
    assert changed(project, seen) == []

    publish(hero, "model")
    assert changed(project, seen) == [Change(hero_model, 1, 2)]
    assert changed(project, seen)[0].label == "hero_model v001 → v002"
    assert stale_build(project, Dependency(hero_model, 1)) == Change(hero_model, 1, 2)
    assert stale_build(project, Dependency(hero_model, 2)) is None


# Catalogs


def test_catalogs_are_added_once_with_stable_ids(tmp_path: Path):
    first = ensure_catalog(tmp_path, "character")
    assert ensure_catalog(tmp_path, "character") == first
    ensure_catalog(tmp_path, "lib/street_kit")
    catalogs = read_catalogs(tmp_path)
    assert [(c.path, c.simple_name) for c in catalogs] == [
        ("character", "character"),
        ("lib/street_kit", "lib-street_kit"),
    ]
    assert "VERSION 1" in (tmp_path / CATALOG_FILE).read_text()
    # Another machine (or folder) gets the same ID for the same catalog.
    other = tmp_path / "other"
    other.mkdir()
    assert ensure_catalog(other, "character") == first


def test_catalogs_made_in_blender_are_kept(tmp_path: Path):
    (tmp_path / CATALOG_FILE).write_text(
        "VERSION 1\n\n0b6e2c1a-1111-4a2b-9c3d-123456789abc:favourites:favourites\n"
    )
    ensure_catalog(tmp_path, "prop")
    assert [c.path for c in read_catalogs(tmp_path)] == ["favourites", "prop"]


def test_the_asset_library_setting(project):
    assert load_config().asset_library == "assets"
