from pathlib import Path

import pytest

from smallstudio_pipeline.core.context import FileContext, file_context


def context_of(project, path: Path) -> FileContext:
    found = file_context(project, path)
    assert found is not None, f"{path} wasn't recognised"
    return found


@pytest.fixture
def entities(project):
    hero = project.create_asset("character", "hero")
    sequence = project.create_sequence("010")
    shot = sequence.create_shot()
    return hero, sequence, shot


def test_asset_files(project, entities):
    hero, _, _ = entities
    work = context_of(project, hero.workfile_path("rigging", 12))
    assert work == FileContext("asset", "hero", "rigging", 12, "work")
    assert work.label == "hero · rigging · v012"
    assert not work.is_publish

    publish = context_of(project, hero.publish_path("rigging", 4))
    assert publish.label == "hero · rigging · publish v004"
    assert publish.is_publish

    hero_file = context_of(project, hero.hero_path("rigging"))
    assert hero_file == FileContext("asset", "hero", "rigging", None, "hero")
    assert hero_file.label == "hero · rigging · published"


def test_sequence_and_shot_files(project, entities):
    _, sequence, shot = entities
    layout = file_context(project, sequence.workfile_path("layout", 3))
    assert layout == FileContext("sequence", "010_010", "layout", 3, "work")
    animation = file_context(project, shot.hero_path("animation"))
    assert animation == FileContext("shot", "010_010_0010", "animation", None, "hero")


def test_asset_names_that_look_like_versions(project):
    tank = project.create_asset("prop", "tank_v2")
    assert file_context(project, tank.hero_path("modeling")) == FileContext(
        "asset", "tank_v2", "modeling", None, "hero"
    )
    assert file_context(project, tank.publish_path("modeling", 1)) == FileContext(
        "asset", "tank_v2", "modeling", 1, "publish"
    )


@pytest.mark.parametrize(
    "relative",
    [
        "assets/character/hero/rigging/work/hero_rigging_v012.blend1",  # Blender's backup.
        "assets/character/hero/rigging/work/scratch.blend",
        "pipeline.toml",
    ],
)
def test_other_files_in_the_project_are_unmanaged(project, entities, relative):
    assert file_context(project, project.root / relative) is None


def test_files_outside_the_project_are_unmanaged(project, tmp_path: Path):
    assert file_context(project, tmp_path / "elsewhere/hero_rigging_v001.blend") is None
