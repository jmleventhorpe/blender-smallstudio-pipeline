import json
from pathlib import Path

import pytest

from smallstudio_pipeline.core.config import load_config
from smallstudio_pipeline.core.errors import MetadataError
from smallstudio_pipeline.core.files import write_atomic
from smallstudio_pipeline.core.metadata import (
    AssetMetadata,
    CastEntry,
    SequenceMetadata,
    ShotMetadata,
    read_metadata,
    write_metadata,
)
from smallstudio_pipeline.core.templates import build_templates
from smallstudio_pipeline.core.tracker import FilesystemTracker


def test_write_atomic_creates_folders_and_leaves_no_temp_file(tmp_path: Path):
    path = tmp_path / "a/b/notes.json"
    write_atomic(path, "first")
    write_atomic(path, "second")
    assert path.read_text() == "second"
    assert sorted(p.name for p in path.parent.iterdir()) == ["notes.json"]


@pytest.mark.parametrize(
    "metadata",
    [
        AssetMetadata("hero", "character", ["model", "rig"]),
        SequenceMetadata("010_020"),
        SequenceMetadata("010_030", title="Opening chase"),
        ShotMetadata(
            "010_020_0030",
            frame_start=1001,
            frame_end=1048,
            casting=[CastEntry("hero", "hero_01"), CastEntry("hero", "hero_02")],
        ),
    ],
)
def test_metadata_round_trips(tmp_path: Path, metadata):
    path = tmp_path / "entity.json"
    write_metadata(path, metadata)
    assert read_metadata(path, type(metadata)) == metadata


def test_older_files_without_optional_fields_still_read(tmp_path: Path):
    path = tmp_path / "shot.json"
    path.write_text(json.dumps({"code": "010_020_0030"}))
    shot = read_metadata(path, ShotMetadata)
    assert shot.frame_start is None
    assert shot.casting == []


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "isn't valid JSON"),
        ("[]", "should hold a JSON object"),
        (json.dumps({"frame_start": 1}), "code is missing"),
        (json.dumps({"code": "010_020_0030", "frame_start": "1001"}), "frame_start should be"),
        (json.dumps({"code": "010_020_0030", "omitted": 1}), "omitted should be true or false"),
        (json.dumps({"code": "010_020_0030", "casting": [{"asset": "hero"}]}), "instance_id"),
        (json.dumps({"code": "010_020_0030", "schema": 99}), "newer version of the tool"),
    ],
)
def test_bad_metadata_files_give_clear_errors(tmp_path: Path, content, message):
    path = tmp_path / "shot.json"
    path.write_text(content)
    with pytest.raises(MetadataError, match=message):
        read_metadata(path, ShotMetadata)


def test_missing_file_gives_a_clear_error(tmp_path: Path):
    with pytest.raises(MetadataError, match="doesn't exist"):
        read_metadata(tmp_path / "nope.json", ShotMetadata)


@pytest.fixture
def tracker(tmp_path: Path) -> FilesystemTracker:
    return FilesystemTracker(tmp_path, build_templates(load_config()))


def test_tracker_saves_and_lists_entities(tracker: FilesystemTracker):
    tracker.save_asset(AssetMetadata("hero", "character", ["model", "rig"]))
    tracker.save_sequence(SequenceMetadata("010_020"))
    tracker.save_shot(ShotMetadata("010_020_0030"))
    assert (tracker.root / "assets/character/hero/hero.json").is_file()
    assert [asset.name for asset in tracker.assets()] == ["hero"]
    assert [sequence.code for sequence in tracker.sequences()] == ["010_020"]
    assert [shot.code for shot in tracker.shots()] == ["010_020_0030"]


def test_tracker_catches_a_copied_metadata_file(tracker: FilesystemTracker):
    tracker.save_asset(AssetMetadata("hero", "character", ["model"]))
    copy = tracker.root / "assets/character/villain/villain.json"
    copy.parent.mkdir(parents=True)
    copy.write_text((tracker.root / "assets/character/hero/hero.json").read_text())
    with pytest.raises(MetadataError, match="sits in the folder for character 'villain'"):
        tracker.assets()
