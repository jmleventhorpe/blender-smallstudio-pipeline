"""Version numbers in file names: hero_rigging_v012.blend."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from .errors import NamingError

PADDING = 3
_VERSION = re.compile(r"_v(\d+)$")


def format_version(number: int, padding: int = PADDING) -> str:
    """Return the version token for a number, e.g. 7 -> 'v007'."""
    if number < 1:
        raise NamingError(f"Versions start at 1, not {number}.")
    return f"v{number:0{padding}d}"


def parse_version(path: Path | str) -> int | None:
    """Return the version in a file name, or None for an unversioned (hero) file."""
    match = _VERSION.search(Path(path).stem)
    return int(match.group(1)) if match else None


def latest_version(paths: Iterable[Path | str]) -> int:
    """Return the highest version among paths, or 0 if none is versioned."""
    versions = (parse_version(path) for path in paths)
    return max((version for version in versions if version is not None), default=0)


def next_version(folder: Path, stem: str) -> int:
    """Return the next free version for stem in folder, starting at 1."""
    return latest_version(folder.glob(f"{stem}_v*.blend")) + 1
