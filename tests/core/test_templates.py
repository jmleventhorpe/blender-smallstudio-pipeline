from pathlib import Path

import pytest

from smallstudio_pipeline.core.config import load_config
from smallstudio_pipeline.core.errors import ConfigError, NamingError
from smallstudio_pipeline.core.templates import build_templates

SAMPLE_VALUES = {
    "asset_type": "character",
    "asset": "street_lamp",
    "task": "rigging",
    "version": 12,
    "episode": "010",
    "sequence": "010_020",
    "shot": "010_020_0030",
}


@pytest.fixture
def templates():
    return build_templates(load_config())


def test_every_default_template_round_trips(templates):
    for template in templates.values():
        values = {key: SAMPLE_VALUES[key] for key in template.keys}
        path = template.format(**values)
        assert template.parse(path) == values, template.name


def test_format_builds_the_expected_paths(templates):
    assert str(templates["asset_work"].format(**SAMPLE_VALUES)) == (
        "assets/character/street_lamp/rigging/work/street_lamp_rigging_v012.blend"
    )
    assert str(
        templates["shot_render"].format(shot="010_020_0030", task="lighting", version=3)
    ) == ("shots/010_020_0030/lighting/render/v003")


def test_render_templates_are_marked(templates):
    assert templates["shot_render"].render
    assert not templates["shot_work"].render


def test_parse_reads_windows_paths(templates):
    path = r"assets\character\hero\rigging\work\hero_rigging_v004.blend"
    assert templates["asset_work"].parse(path)["version"] == 4


def test_parse_rejects_paths_that_do_not_fit(templates):
    work = templates["asset_work"]
    # The file name must repeat the folder's asset name.
    assert work.parse("assets/character/hero/rigging/work/villain_rigging_v001.blend") is None
    assert work.parse("assets/character/hero/rigging/publish/hero_rigging_v001.blend") is None
    assert work.parse("assets/vehicle/hero/rigging/work/hero_rigging_v001.blend") is None


def test_hero_template_does_not_match_versioned_files(templates):
    hero = templates["asset_hero"]
    assert hero.parse("assets/character/hero/rigging/publish/hero_rigging.blend") is not None
    assert hero.parse("assets/character/hero/rigging/publish/hero_rigging_v002.blend") is None


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"asset": "Hero"}, "'Hero' isn't a valid asset"),
        ({"task": "painting"}, "'painting' isn't a valid task"),
        ({"asset_type": "vehicle"}, "'vehicle' isn't a valid asset type"),
    ],
)
def test_format_rejects_bad_values(templates, values, message):
    with pytest.raises(NamingError, match=message):
        templates["asset_work"].format(**{**SAMPLE_VALUES, **values})


def test_format_needs_every_field(templates):
    with pytest.raises(NamingError, match="needs a task"):
        templates["asset_work"].format(asset_type="character", asset="hero", version=1)


def test_find_lists_matching_files(templates, tmp_path: Path):
    folder = tmp_path / "assets/character/hero/rigging/work"
    folder.mkdir(parents=True)
    for name in ("hero_rigging_v001.blend", "hero_rigging_v003.blend", "notes.txt"):
        (folder / name).touch()
    found = templates["asset_work"].find(
        tmp_path, asset_type="character", asset="hero", task="rigging"
    )
    assert [fields["version"] for _, fields in found] == [1, 3]


def test_shot_codes_follow_the_episodes_setting(tmp_path):
    (tmp_path / "pipeline.toml").write_text("[project]\nepisodes = false\n")
    templates = build_templates(load_config(tmp_path))
    assert templates["shot_metadata"].parse("shots/020_0030/020_0030.json") is not None
    assert templates["shot_metadata"].parse("shots/010_020_0030/010_020_0030.json") is None


@pytest.mark.parametrize(
    ("templates_toml", "message"),
    [
        ('asset_work = "assets/{colour}.blend"', r"uses \{colour\}"),
        ('asset_work = "{@nowhere}/x.blend"', r"includes \{@nowhere\}, which doesn't exist"),
        ('asset_folder = "{@asset_work}"', "includes itself"),
    ],
)
def test_bad_templates_give_clear_errors(tmp_path, templates_toml, message):
    (tmp_path / "pipeline.toml").write_text(f"[templates]\n{templates_toml}\n")
    with pytest.raises(ConfigError, match=message):
        build_templates(load_config(tmp_path))
