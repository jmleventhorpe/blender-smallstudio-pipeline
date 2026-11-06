"""What's out of date: publishes published again since a file saw them.

Every publish's record carries its version, so this needs no Blender. changed() compares
a file's linked publishes with the versions seen when it opened (or last looked). The
Blender side, loading/blender/updates.py, reloads libraries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...common.errors import MetadataError
from ...project.core.project import Project
from ...publishing.core.publishing import read_record, record_path


@dataclass(frozen=True)
class Change:
    path: str  # The publish, relative to the project root.
    old: int | None  # The version the file had, if known.
    new: int | None  # The version on disk now.
    padding: int = 3

    @property
    def name(self) -> str:
        """The publish's file name without its extension, e.g. "hero_rig"."""
        return Path(self.path).stem

    @property
    def versions(self) -> str:
        """e.g. "v003 → v004"."""
        return f"{self._version(self.old)} → {self._version(self.new)}"

    @property
    def label(self) -> str:
        """e.g. "hero_rig v003 → v004"."""
        return f"{self.name} {self.versions}"

    def _version(self, number: int | None) -> str:
        return "unknown" if number is None else f"v{number:0{self.padding}d}"


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
            changes.append(Change(path, old, new, project.config.version_padding))
    return changes
