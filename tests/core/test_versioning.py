from pathlib import Path

import pytest

from smallstudio_pipeline.core.errors import NamingError
from smallstudio_pipeline.core.versioning import (
    format_version,
    latest_version,
    next_version,
    parse_version,
)


def test_format_version_pads_to_three_digits():
    assert format_version(7) == "v007"
    assert format_version(1234) == "v1234"


def test_format_version_rejects_zero():
    with pytest.raises(NamingError):
        format_version(0)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("hero_rigging_v012.blend", 12),
        ("010_010_0010_animation_v007.blend", 7),
        ("hero_rigging.blend", None),
        ("v003_notes.blend", None),
    ],
)
def test_parse_version(name, expected):
    assert parse_version(name) == expected


def test_latest_version_ignores_hero_files():
    assert latest_version(["hero_rigging.blend", "hero_rigging_v002.blend"]) == 2
    assert latest_version(["hero_rigging.blend"]) == 0


def test_next_version_counts_from_files_on_disk(tmp_path: Path):
    assert next_version(tmp_path, "hero_rigging") == 1
    for name in (
        "hero_rigging_v001.blend",
        "hero_rigging_v004.blend",
        "villain_rigging_v009.blend",
    ):
        (tmp_path / name).touch()
    assert next_version(tmp_path, "hero_rigging") == 5
