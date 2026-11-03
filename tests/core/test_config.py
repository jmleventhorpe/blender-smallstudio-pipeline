from pathlib import Path

import pytest

from smallstudio_pipeline.core.config import load_config
from smallstudio_pipeline.core.errors import ConfigError


def write_project_config(root: Path, text: str) -> Path:
    path = root / "pipeline.toml"
    path.write_text(text)
    return path


def test_defaults_load():
    config = load_config()
    assert config.fps == 24
    assert config.shot_start == 101
    assert config.resolution == (1920, 1080)
    assert config.episodes is True
    assert set(config.asset_types) == {"character", "prop", "set", "lib", "utility"}
    assert [task.name for task in config.tasks.values() if task.entity == "sequence"] == [
        "layout",
        "light",
    ]
    assert config.tasks["light"].renders == "shot"
    assert config.tasks["light"].publishes is False


def test_prop_rig_is_optional():
    prop = load_config().asset_types["prop"]
    assert prop.required_tasks == ("model",)
    assert prop.shot_link == ("rig", "model")


def test_a_project_without_pipeline_toml_gets_the_defaults(tmp_path):
    assert load_config(tmp_path) == load_config()


def test_project_settings_merge_table_by_table(tmp_path):
    write_project_config(
        tmp_path,
        """
        [project]
        fps = 25

        [asset_types.prop]
        shot_link = ["model"]

        [asset_types.vehicle]
        tasks = ["model", "rig"]
        shot_link = ["rig"]
        """,
    )
    config = load_config(tmp_path)
    assert config.fps == 25
    assert config.resolution == (1920, 1080)  # Untouched default.
    assert config.asset_types["prop"].tasks == ("model", "rig")
    assert config.asset_types["prop"].shot_link == ("model",)
    assert "vehicle" in config.asset_types


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('[project]\nfps = "24"', "project.fps should be a whole number"),
        ("[project]\nepisodes = 1", "project.episodes should be true or false"),
        ("[project]\nfps = true", "project.fps should be a whole number"),
        ("[project]\nresolution = [1920]", r"project.resolution should be \[width, height\]"),
        ("[naming]\nname_pattern = '[a-z'", "naming.name_pattern isn't a valid pattern"),
        ("[naming]\ncode_step = 1", "naming.code_step should be at least 2"),
        ('[tasks.paint]\nentity = "frame"', "tasks.paint.entity should be one of"),
        ('[tasks.paint]\nentity = "shot"\nrenders = "asset"', "tasks.paint.renders should be"),
        (
            '[asset_types.prop]\nshot_link = ["rigg"]',
            "asset_types.prop.shot_link: 'rigg' isn't one of prop's tasks",
        ),
        (
            '[asset_types.prop]\ntasks = ["layout"]',
            "asset_types.prop.tasks: 'layout' isn't an asset task",
        ),
        (
            '[asset_types.prop]\nshot_link = ["rig"]',
            "asset_types.prop.shot_link needs at least one task that isn't optional",
        ),
        ('[asset_types.Big]\ntasks = ["model"]\nshot_link = ["model"]', "doesn't match"),
        ("[templates]\nasset_work = 3", "templates.asset_work should be text"),
        ("[project\nfps = 24", "isn't valid TOML"),
    ],
)
def test_bad_settings_give_clear_errors(tmp_path, text, message):
    project_file = write_project_config(tmp_path, text)
    with pytest.raises(ConfigError, match=message) as error:
        load_config(tmp_path)
    assert str(project_file) in str(error.value)
