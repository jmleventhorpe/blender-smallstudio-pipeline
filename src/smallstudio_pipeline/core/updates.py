"""What's out of date: linked publishes that moved on, and builds from an older publish."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import MetadataError
from .project import Project
from .publishing import Dependency, read_record, record_path


@dataclass(frozen=True)
class Change:
    path: str  # The publish, relative to the project root.
    old: int | None  # The version the file had, if known.
    new: int | None  # The version on disk now.

    @property
    def label(self) -> str:
        """e.g. "hero_rig v003 → v004"."""
        return f"{Path(self.path).stem} {_version(self.old)} → {_version(self.new)}"


def publish_version(project: Project, path: str) -> int | None:
    """The version of a publish (usually a hero file) from its record, or None if unknown."""
    record = record_path(project.root / path)
    if not record.exists():
        return None
    try:
        return read_record(record).version
    except MetadataError:
        return None


def changed(project: Project, seen: dict[str, int | None]) -> list[Change]:
    """Publishes whose version differs from the one seen (e.g. when the file was opened)."""
    changes = []
    for path, old in sorted(seen.items()):
        new = publish_version(project, path)
        if new != old:
            changes.append(Change(path, old, new))
    return changes


def stale_build(project: Project, built_from: Dependency) -> Change | None:
    """A Change if the publish something was built from has been published again since."""
    new = publish_version(project, built_from.path)
    if new is not None and built_from.version is not None and new > built_from.version:
        return Change(built_from.path, built_from.version, new)
    return None


def _version(number: int | None) -> str:
    return "unknown" if number is None else f"v{number:03d}"
