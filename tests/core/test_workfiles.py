from pathlib import Path

import pytest

from smallstudio_pipeline.core.errors import ConfigError, PipelineError
from smallstudio_pipeline.core.workfiles import new_workfile, version_up_path


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def test_new_workfile_starts_at_v001_with_no_starter(project):
    hero = project.create_asset("character", "hero")
    plan = new_workfile(hero, "model")
    assert plan.path == hero.workfile_path("model", 1)
    assert plan.starter is None


def test_new_workfile_uses_the_tasks_starter_file(make_project):
    project = make_project('[tasks.layout]\nstarter = "starters/layout.blend"\n')
    touch(project.root / "starters/layout.blend")
    plan = new_workfile(project.create_sequence("010"), "layout")
    assert plan.starter == project.root / "starters/layout.blend"


def test_a_missing_starter_file_is_reported(make_project):
    project = make_project('[tasks.layout]\nstarter = "starters/layout.blend"\n')
    with pytest.raises(PipelineError, match=r"layout starter file .* doesn't exist"):
        new_workfile(project.create_sequence("010"), "layout")


def test_new_workfile_refuses_when_the_task_has_workfiles(project):
    hero = project.create_asset("character", "hero")
    touch(hero.workfile_path("rig", 3))
    with pytest.raises(PipelineError, match=r"hero_rig_v003\.blend"):
        new_workfile(hero, "rig")


def test_new_workfile_only_for_the_entitys_tasks(project):
    with pytest.raises(PipelineError, match="has no anim task"):
        new_workfile(project.create_sequence("010"), "anim")


def test_version_up_goes_to_the_next_free_version(project):
    hero = project.create_asset("character", "hero")
    for version in (1, 2, 5):
        touch(hero.workfile_path("rig", version))
    # Versioning up from v002 skips past v005, which someone else saved.
    assert version_up_path(project, hero.workfile_path("rig", 2)) == hero.workfile_path("rig", 6)


def test_version_up_refuses_publishes_and_other_files(project):
    hero = project.create_asset("character", "hero")
    with pytest.raises(PipelineError, match="read-only"):
        version_up_path(project, hero.hero_path("rig"))
    with pytest.raises(PipelineError, match="isn't a pipeline workfile"):
        version_up_path(project, project.root / "scratch.blend")


def test_entities_by_category(project):
    project.create_asset("character", "hero")
    project.create_asset("prop", "crate")
    project.create_sequence("010").create_shot()
    assert project.categories()[-2:] == ["sequence", "shot"]
    assert [asset.name for asset in project.entities_in("prop")] == ["crate"]
    assert [str(shot.code) for shot in project.entities_in("shot")] == ["010_010_0010"]
    assert project.entity("asset", "hero").label == "hero"
    assert project.entity("shot", "010_010_0010").label == "shot 010_010_0010"


def test_tasks_with_workfiles(project):
    hero = project.create_asset("character", "hero")
    sequence = project.create_sequence("010")
    assert hero.tasks_with_workfiles() == []
    touch(hero.workfile_path("rig", 1))
    touch(sequence.workfile_path("light", 1))
    assert hero.tasks_with_workfiles() == ["rig"]
    assert sequence.tasks == ["layout", "light"]
    assert sequence.tasks_with_workfiles() == ["light"]


def test_asset_types_cannot_be_called_sequence_or_shot(make_project):
    with pytest.raises(ConfigError, match="can't be an asset type name"):
        make_project('[asset_types.shot]\ntasks = ["model"]\nshot_link = ["model"]\n')
