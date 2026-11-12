from pathlib import Path

import pytest

from smallstudio_pipeline.common.errors import ConfigError, PipelineError
from smallstudio_pipeline.workfiles.core.workfiles import next_workfile_path, version_up_path


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def test_new_workfiles_go_to_the_tasks_next_free_version(project):
    hero = project.create_asset("character", "hero")
    assert next_workfile_path(hero, "model") == hero.workfile_path("model", 1)
    touch(hero.workfile_path("model", 3))
    assert next_workfile_path(hero, "model") == hero.workfile_path("model", 4)


def test_workfiles_only_for_the_entitys_tasks(project):
    with pytest.raises(PipelineError, match="has no model task"):
        next_workfile_path(project.create_sequence("010"), "model")


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
    assert project.categories()[-1] == "sequence"  # No task works per shot by default.
    assert [asset.name for asset in project.entities_in("prop")] == ["crate"]
    assert [str(shot.code) for shot in project.entities_in("shot")] == ["010_010_0010"]
    assert project.entity("asset", "hero").label == "hero"
    assert project.entity("shot", "010_010_0010").label == "shot 010_010_0010"


def test_shots_are_browsed_when_a_task_works_per_shot(make_project):
    project = make_project('[tasks.paint]\nentity = "shot"\n')
    assert project.categories()[-2:] == ["sequence", "shot"]


def test_tasks_with_workfiles(project):
    hero = project.create_asset("character", "hero")
    sequence = project.create_sequence("010")
    assert hero.tasks_with_workfiles() == []
    touch(hero.workfile_path("rig", 1))
    touch(sequence.workfile_path("light", 1))
    assert hero.tasks_with_workfiles() == ["rig"]
    assert sequence.tasks == ["layout", "light", "anim"]
    assert sequence.tasks_with_workfiles() == ["light"]


def test_asset_types_cannot_be_called_sequence_or_shot(make_project):
    with pytest.raises(ConfigError, match="can't be an asset type name"):
        make_project('[asset_types.shot]\ntasks = ["model"]\n')
