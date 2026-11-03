from pathlib import Path

import pytest

from smallstudio_pipeline.core.errors import (
    EntityExists,
    EntityNotFound,
    NamingError,
    PipelineError,
)
from smallstudio_pipeline.core.project import Project


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


# Projects


def test_create_writes_a_pipeline_toml(project):
    assert (project.root / "pipeline.toml").is_file()
    with pytest.raises(EntityExists):
        Project.create(project.root)


def test_find_walks_up_to_the_project(project):
    deep = project.root / "assets/character/hero/rig/work"
    deep.mkdir(parents=True)
    found = Project.find(deep)
    assert found is not None and found.root == project.root
    assert Project.find(project.root.parent) is None


# Assets


def test_create_asset_with_required_tasks(project):
    hero = project.create_asset("character", "hero")
    crate = project.create_asset("prop", "crate")
    assert hero.tasks == ["model", "rig"]
    assert crate.tasks == ["model"]  # Rigging is optional for props.
    assert (project.root / "assets/character/hero/hero.json").is_file()


def test_create_asset_with_an_optional_task(project):
    lamp = project.create_asset("prop", "lamp", tasks=["rig"])
    assert lamp.tasks == ["model", "rig"]


@pytest.mark.parametrize(
    ("asset_type", "name", "tasks", "error", "message"),
    [
        ("character", "Hero", None, NamingError, "isn't a valid name"),
        ("vehicle", "car", None, PipelineError, "'vehicle' isn't an asset type"),
        ("set", "street", ["rig"], PipelineError, "set assets don't have a rig task"),
    ],
)
def test_create_asset_rejects_bad_input(project, asset_type, name, tasks, error, message):
    with pytest.raises(error, match=message):
        project.create_asset(asset_type, name, tasks)


def test_asset_names_are_unique_across_types(project):
    project.create_asset("character", "hero")
    with pytest.raises(EntityExists, match="unique"):
        project.create_asset("prop", "hero")


def test_assets_are_listed_sorted_and_by_type(project):
    for asset_type, name in [("prop", "crate"), ("character", "hero"), ("prop", "bucket")]:
        project.create_asset(asset_type, name)
    assert [asset.name for asset in project.assets()] == ["bucket", "crate", "hero"]
    assert [asset.name for asset in project.assets("prop")] == ["bucket", "crate"]


def test_asset_lookup_suggests_close_names(project):
    project.create_asset("character", "hero")
    assert project.asset("hero").asset_type == "character"
    with pytest.raises(EntityNotFound, match="Did you mean 'hero'"):
        project.asset("heros")


def test_shot_task_follows_the_assets_tasks(project):
    crate = project.create_asset("prop", "crate")
    assert crate.shot_task() == "model"
    crate.add_task("rig")
    assert project.asset("crate").shot_task() == "rig"  # Saved, not just in memory.
    with pytest.raises(PipelineError, match="already has"):
        crate.add_task("rig")


def test_asset_workfile_and_publish_paths(project):
    hero = project.create_asset("character", "hero")
    folder = project.root / "assets/character/hero/rig"
    assert hero.workfile_path("rig", 12) == folder / "work/hero_rig_v012.blend"
    assert hero.publish_path("rig", 4) == folder / "publish/hero_rig_v004.blend"
    assert hero.hero_path("rig") == folder / "publish/hero_rig.blend"


def test_versions_come_from_files_on_disk(project):
    hero = project.create_asset("character", "hero")
    assert hero.next_workfile_version("rig") == 1
    assert hero.latest_publish_version("rig") is None
    for version in (1, 2, 5):
        touch(hero.workfile_path("rig", version))
    touch(hero.publish_path("rig", 3))
    touch(hero.hero_path("rig"))  # The hero file isn't a version.
    assert hero.workfile_versions("rig") == [1, 2, 5]
    assert hero.next_workfile_version("rig") == 6
    assert hero.latest_publish_version("rig") == 3
    assert hero.next_publish_version("rig") == 4


def test_asset_paths_only_for_its_own_tasks(project):
    crate = project.create_asset("prop", "crate")
    with pytest.raises(PipelineError, match="crate has no rig task"):
        crate.workfile_path("rig", 1)


# Sequences and shots


def test_sequences_number_in_steps_with_an_optional_title(project):
    project.create_sequence("010")
    second = project.create_sequence("010", title=" Opening chase ")
    assert [str(seq.code) for seq in project.sequences()] == ["010_010", "010_020"]
    assert project.sequence("010_020").title == second.title == "Opening chase"
    assert project.sequence("010_010").title == ""
    project.create_sequence("020")
    assert project.episodes() == ["010", "020"]
    assert [str(seq.code) for seq in project.sequences("020")] == ["020_010"]


def test_shots_can_go_before_the_first(project):
    sequence = project.create_sequence("010")
    sequence.create_shot()
    assert str(sequence.create_shot(first=True).code) == "010_010_0005"


def test_new_episodes_number_in_steps(project):
    assert project.next_episode() == "010"
    project.create_sequence("010")
    assert project.next_episode() == "020"


def test_sequences_need_an_episode_when_the_project_uses_them(project):
    with pytest.raises(PipelineError, match="uses episodes"):
        project.create_sequence()


def test_projects_without_episodes(make_project):
    project = make_project("[project]\nepisodes = false\n")
    sequence = project.create_sequence()
    shot = sequence.create_shot()
    assert str(shot.code) == "010_0010"
    with pytest.raises(PipelineError, match="doesn't use episodes"):
        project.create_sequence("010")


def test_shots_number_in_steps_and_insert(project):
    sequence = project.create_sequence("010")
    first = sequence.create_shot()
    sequence.create_shot()
    sequence.create_shot(after=first)
    assert [str(shot.code) for shot in sequence.shots()] == [
        "010_010_0010",
        "010_010_0015",
        "010_010_0020",
    ]
    assert project.shot("010_010_0015").sequence == sequence


def test_omitted_shots_are_hidden_but_keep_their_number(project):
    sequence = project.create_sequence("010")
    sequence.create_shot()
    last = sequence.create_shot()
    last.omit()
    assert [str(shot.code) for shot in sequence.shots()] == ["010_010_0010"]
    assert project.shot("010_010_0020").omitted
    assert str(sequence.create_shot().code) == "010_010_0030"


def test_shot_lookup_suggests_close_codes(project):
    project.create_sequence("010").create_shot()
    with pytest.raises(EntityNotFound, match="Did you mean '010_010_0010'"):
        project.shot("010_010_0011")


def test_frame_range_comes_from_metadata(project):
    shot = project.create_sequence("010").create_shot()
    assert shot.frame_range is None
    shot.metadata.frame_start, shot.metadata.frame_end = 1001, 1048
    shot.save()
    assert project.shot(str(shot.code)).frame_range == (1001, 1048)


# Tasks per entity: where each department's files go


def test_sequence_tasks(project):
    sequence = project.create_sequence("010")
    folder = project.root / "sequences/010_010"
    assert sequence.workfile_path("layout", 3) == folder / "layout/work/010_010_layout_v003.blend"
    assert sequence.hero_path("layout") == folder / "layout/publish/010_010_layout.blend"
    assert sequence.render_path("layout", 3) == folder / "layout/render/v003"
    assert sequence.workfile_path("light", 1).parent == folder / "light/work"
    with pytest.raises(PipelineError, match="light doesn't publish"):
        sequence.publish_path("light", 1)
    with pytest.raises(PipelineError, match="light doesn't render per sequence"):
        sequence.render_path("light", 1)
    with pytest.raises(PipelineError, match="has no anim task"):
        sequence.workfile_path("anim", 1)


def test_shot_tasks(project):
    shot = project.create_sequence("010").create_shot()
    folder = project.root / "shots/010_010_0010"
    assert shot.workfile_path("anim", 7).name == "010_010_0010_anim_v007.blend"
    assert shot.hero_path("anim") == folder / "anim/publish/010_010_0010_anim.blend"
    assert shot.render_path("anim", 7) == folder / "anim/render/v007"
    assert shot.render_path("light", 2) == folder / "light/render/v002"
    with pytest.raises(PipelineError, match="has no light task"):
        shot.workfile_path("light", 1)  # Lighting is worked on in the sequence file.


@pytest.mark.parametrize("relative", [True, False])
def test_renders_resolve_under_render_root(make_project, tmp_path, relative):
    render_root = "renders" if relative else str(tmp_path / "farm")
    project = make_project(f'[project]\nrender_root = "{render_root}"\n')
    shot = project.create_sequence("010").create_shot()
    expected_root = project.root / "renders" if relative else tmp_path / "farm"
    assert shot.render_path("light", 1) == expected_root / "shots/010_010_0010/light/render/v001"
    assert shot.workfile_path("anim", 1).is_relative_to(project.root)
