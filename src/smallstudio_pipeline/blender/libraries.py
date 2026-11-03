"""Linked and appended libraries: loading datablocks from publishes."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import bpy


def load(path: Path, kind: str, names: Iterable[str], link: bool, **options: Any) -> dict[str, Any]:
    """Link or append datablocks of one kind ("collections", "objects", "materials"…) by
    name. Returns {name asked for: datablock}, without names the file doesn't have.

    The datablock's own name can differ: appending next to a local "skin" gives "skin.001".
    """
    # The stubs say load() returns None, so it's typed loosely here, in one place.
    loader: Any = bpy.data.libraries.load(str(path), link=link, **options)
    with loader as (data_from, data_to):
        available = set(getattr(data_from, kind))
        wanted = [name for name in names if name in available]
        # A copy: Blender swaps the names in this list for the datablocks, in place.
        setattr(data_to, kind, list(wanted))
    # Blender fills the list in the order the names were given.
    loaded = zip(wanted, getattr(data_to, kind), strict=True)
    return {name: datablock for name, datablock in loaded if datablock is not None}
