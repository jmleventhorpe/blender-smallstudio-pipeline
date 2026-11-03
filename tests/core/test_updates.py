from smallstudio_pipeline.core.publishing import (
    Dependency,
    new_record,
    plan_publish,
    write_records,
)
from smallstudio_pipeline.core.updates import Change, changed, stale_build

HERO_MODEL = "assets/character/hero/model/publish/hero_model.blend"


def publish(asset, version_count=1):
    """Write publish records for the asset's model, as if published that many times."""
    for _ in range(version_count):
        plan = plan_publish(asset, "model")
        plan.path.parent.mkdir(parents=True, exist_ok=True)
        plan.path.touch()
        write_records(plan, new_record(plan, asset.workfile_path("model", 1), "5.2.2", []))


def test_changed_lists_publishes_whose_version_moved(project):
    hero = project.create_asset("character", "hero")
    publish(hero, 2)
    assert changed(project, {HERO_MODEL: 1}) == [Change(HERO_MODEL, 1, 2)]
    assert changed(project, {HERO_MODEL: 2}) == []


def test_a_build_from_an_older_publish_is_stale(project):
    hero = project.create_asset("character", "hero")
    publish(hero, 2)
    assert stale_build(project, Dependency(HERO_MODEL, 1)) == Change(HERO_MODEL, 1, 2)
    assert stale_build(project, Dependency(HERO_MODEL, 2)) is None


def test_labels_follow_the_projects_version_padding(make_project):
    project = make_project("[naming]\nversion_padding = 4\n")
    hero = project.create_asset("character", "hero")
    publish(hero, 2)
    (change,) = changed(project, {HERO_MODEL: 1})
    assert change.label == "hero_model v0001 → v0002"
    assert Change(HERO_MODEL, None, 2).versions == "unknown → v002"
