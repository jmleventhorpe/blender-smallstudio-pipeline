"""Entity metadata: one small JSON file per asset, sequence and shot.

AssetMetadata (name, type, tasks), SequenceMetadata (code) and ShotMetadata (frame
range, cut, casting, omitted) are plain dataclasses. read_metadata() checks a file field
by field and says what's wrong; write_metadata() writes it atomically. Each file carries
a schema number, so the format can change later without breaking existing projects.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .errors import MetadataError
from .files import write_atomic
from .reading import get, get_names

# Bump when the file layout changes, and teach from_dict to read the old one.
SCHEMA = 1


@dataclass
class AssetMetadata:
    name: str
    asset_type: str
    tasks: list[str]
    schema: int = SCHEMA

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetMetadata:
        return cls(
            name=get(data, "name", str),
            asset_type=get(data, "asset_type", str),
            tasks=get_names(data, "tasks"),
            schema=_schema(data),
        )


@dataclass
class SequenceMetadata:
    code: str
    schema: int = SCHEMA

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SequenceMetadata:
        return cls(code=get(data, "code", str), schema=_schema(data))


@dataclass
class CastEntry:
    asset: str
    instance_id: str  # e.g. "hero_01"; stable once assigned.


@dataclass
class ShotMetadata:
    code: str
    frame_start: int | None = None  # Frame range and cut are written by layout publish.
    frame_end: int | None = None
    cut_in: int | None = None
    cut_out: int | None = None
    casting: list[CastEntry] = field(default_factory=list)
    omitted: bool = False
    schema: int = SCHEMA

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShotMetadata:
        casting = get(data, "casting", list, default=[])
        return cls(
            code=get(data, "code", str),
            frame_start=get(data, "frame_start", int, default=None),
            frame_end=get(data, "frame_end", int, default=None),
            cut_in=get(data, "cut_in", int, default=None),
            cut_out=get(data, "cut_out", int, default=None),
            casting=[
                CastEntry(get(entry, "asset", str), get(entry, "instance_id", str))
                for entry in casting
            ],
            omitted=get(data, "omitted", bool, default=False),
            schema=_schema(data),
        )


def read_metadata[M: (AssetMetadata, SequenceMetadata, ShotMetadata)](
    path: Path, kind: type[M]
) -> M:
    """Read an entity's metadata file, or raise MetadataError saying what's wrong."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MetadataError(f"{path} doesn't exist.") from None
    except json.JSONDecodeError as error:
        raise MetadataError(f"{path} isn't valid JSON: {error}.") from None
    try:
        if not isinstance(data, dict):
            raise ValueError("it should hold a JSON object")
        return kind.from_dict(data)
    except ValueError as error:
        raise MetadataError(f"{path}: {error}.") from None


def write_metadata(path: Path, metadata: AssetMetadata | SequenceMetadata | ShotMetadata) -> None:
    write_atomic(path, json.dumps(asdict(metadata), indent=2) + "\n")


def _schema(data: dict[str, Any]) -> int:
    schema = get(data, "schema", int, default=SCHEMA)
    if schema > SCHEMA:
        raise ValueError("it was written by a newer version of the tool; update the add-on")
    return schema
