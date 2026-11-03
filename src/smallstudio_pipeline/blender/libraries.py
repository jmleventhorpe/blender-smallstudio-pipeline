"""Libraries: loading from publishes, what a file links, updates and the Asset Browser."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import bpy

from ..core.entities import Project
from ..core.publishing import relative
from ..core.updates import Change, changed, publish_version, stale_build
from .identity import built_from


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


# The publishes this file links, and their versions when it was opened (or last updated).
seen: dict[str, int | None] = {}


def linked_publishes(project: Project) -> dict[str, bpy.types.Library]:
    """The libraries this file links from inside the project, by path relative to it."""
    found = {}
    for library in bpy.data.libraries:
        path = Path(bpy.path.abspath(library.filepath)).resolve()
        if path.is_relative_to(project.root):
            found[relative(project, path)] = library
    return found


def remember_versions(project: Project) -> None:
    """Note the version of every linked publish, to tell later what's changed."""
    seen.clear()
    seen.update({path: publish_version(project, path) for path in linked_publishes(project)})


def reload_changed(project: Project) -> list[Change]:
    """Reload linked publishes that have been published again since they were seen."""
    changes = changed(project, seen)
    libraries = linked_publishes(project)
    for change in changes:
        libraries[change.path].reload()
        seen[change.path] = change.new
    return changes


def stale_builds(project: Project, scene: bpy.types.Scene) -> list[Change]:
    """Asset roots built from a publish that has moved on since (a rig from an older model)."""
    found = []
    for root in scene.collection.children_recursive:
        source = built_from(root)
        change = stale_build(project, source) if source else None
        if change is not None:
            found.append(change)
    return found


def register_asset_library(project: Project) -> bool:
    """Add the project's asset folder to Blender's asset libraries, linking by default.

    Returns True if it was added. This changes Blender's preferences.
    """
    folder = (project.root / project.config.asset_library).resolve()
    libraries = bpy.context.preferences.filepaths.asset_libraries
    if any(Path(bpy.path.abspath(lib.path)).resolve() == folder for lib in libraries):
        return False
    library = libraries.new(name=project.root.name, directory=str(folder))
    library.import_method = "LINK"
    return True
