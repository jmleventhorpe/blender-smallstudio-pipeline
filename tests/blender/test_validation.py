"""Runs inside Blender (see run.py): publish-validator with the pipeline's checks."""

import bpy
import pytest
from conftest import add_cube
from publish_validator import FAILED, PASSED, SKIPPED

from smallstudio_pipeline.project.blender.identity import (
    ASSET_TYPE,
    INSTANCE_ID,
    create_root_collection,
)
from smallstudio_pipeline.publishing.blender.validation import subject_for, validator_for
from smallstudio_pipeline.publishing.core.publishing import PublishTarget


@pytest.fixture
def hero(project):
    """hero's model: a root collection with one clean cube in it."""
    asset = project.create_asset("character", "hero")
    root = create_root_collection(asset, bpy.context.scene)
    add_cube(root, "body")
    return asset, root


def run(hero, fix=False):
    asset, root = hero
    subject = subject_for(root, PublishTarget(asset, "model"))
    return validator_for(asset.project).run(subject, fix=fix)


def result(report, check_id):
    found = report.get(check_id)
    assert found is not None, f"{check_id} didn't run"
    return found


def statuses(report):
    return {r.check_id: r.status for r in report.results if r.status != PASSED}


def test_a_clean_asset_passes(hero):
    report = run(hero)
    print(report.as_text())
    assert report.passed
    assert report.load_errors == []
    assert result(report, "GroupSetup").status == SKIPPED  # Off in the pipeline's settings.


def test_number_endings_and_a_renamed_root_block_the_publish(hero):
    _, root = hero
    add_cube(root, "body.001")
    root.name = "hero_copy"
    report = run(hero)
    assert not report.passed
    assert statuses(report)["NoNumberEndings"] == FAILED
    assert statuses(report)["AssetRoot"] == FAILED


def test_identity_and_instance_id_problems_and_their_fixes(hero):
    _, root = hero
    root[ASSET_TYPE] = "prop"
    del root[INSTANCE_ID]
    report = run(hero)
    assert statuses(report)["AssetRoot"] == FAILED
    assert statuses(report)["InstanceIdDeclared"] == FAILED

    root[ASSET_TYPE] = "character"
    fixed = run(hero, fix=True)
    assert fixed.passed
    assert root.is_property_overridable_library(f'["{INSTANCE_ID}"]')


def test_removed_objects_warn(hero, monkeypatch):
    from smallstudio_pipeline.publishing.blender import validation
    from smallstudio_pipeline.publishing.core.publishing import PublishRecord

    previous = PublishRecord.__new__(PublishRecord)
    previous.version, previous.object_names = 3, ["body", "eyes"]
    monkeypatch.setattr(validation, "hero_record", lambda asset, task: previous)
    report = run(hero)
    assert report.passed
    assert [i.message for i in result(report, "StableNames").issues] == [
        "eyes was in v003 but isn't now"
    ]


def test_a_projects_own_settings_and_checks(hero, project):
    (project.root / "validation.toml").write_text("[checks.Ngons]\nenabled = false\n")
    checks = project.root / "checks" / "blender"
    checks.mkdir(parents=True)
    (checks / "studio.py").write_text(
        "from publish_validator import Check\n\n"
        "class NoCubesNamedBody(Check):\n"
        "    hosts = ['blender']\n"
        "    def validate(self, ctx):\n"
        "        if any(o.name == 'body' for o in ctx.host.objects(ctx.root)):\n"
        "            yield 'body is a cube'\n"
    )
    report = run(hero)
    assert result(report, "Ngons").status == SKIPPED
    assert result(report, "NoCubesNamedBody").status == FAILED
