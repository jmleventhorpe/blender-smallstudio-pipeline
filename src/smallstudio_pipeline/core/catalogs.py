"""Asset catalogs: Blender keeps them in blender_assets.cats.txt at an asset library's root.

Blender has no Python API for catalogs, so the pipeline reads and writes the file itself.
Each line is "uuid:path:simple_name", e.g. "1f0c...:character:character".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from .files import write_atomic

CATALOG_FILE = "blender_assets.cats.txt"
HEADER = """\
# This is an Asset Catalog Definition file for Blender.
#
# Empty lines and lines starting with `#` will be ignored.
# The first non-ignored line should be the version indicator.
# Other lines are of the format "UUID:catalog/path/for/assets:simple catalog name"

VERSION 1

"""
# Catalog IDs come from their paths, so every machine and publish agrees on them.
_NAMESPACE = uuid.UUID("6a1c3f0e-2b7d-4e59-9c84-3d5f1a2b7e60")


@dataclass(frozen=True)
class Catalog:
    id: uuid.UUID
    path: str  # e.g. "character", or "lib/street_kit"
    simple_name: str


def read_catalogs(library_root: Path) -> list[Catalog]:
    path = library_root / CATALOG_FILE
    if not path.exists():
        return []
    catalogs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "VERSION")):
            continue
        catalog_id, catalog_path, simple_name = line.split(":", 2)
        catalogs.append(Catalog(uuid.UUID(catalog_id), catalog_path, simple_name))
    return catalogs


def ensure_catalog(library_root: Path, catalog_path: str) -> uuid.UUID:
    """Return the catalog's ID, adding it to the library's catalog file if it's new.

    Catalogs added in Blender's UI are kept as they are.
    """
    catalogs = read_catalogs(library_root)
    for catalog in catalogs:
        if catalog.path == catalog_path:
            return catalog.id
    catalog_id = uuid.uuid5(_NAMESPACE, catalog_path)
    catalogs.append(Catalog(catalog_id, catalog_path, catalog_path.replace("/", "-")))
    lines = [f"{c.id}:{c.path}:{c.simple_name}" for c in catalogs]
    write_atomic(library_root / CATALOG_FILE, HEADER + "\n".join(lines) + "\n")
    return catalog_id
