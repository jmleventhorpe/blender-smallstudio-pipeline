"""Keeping a file's links current: the Blender side of core/updates.py.

remember_versions() notes, when a file opens, the version of every publish it links;
reload_changed() (Check Updates) reloads the ones published again since; stale_builds()
finds roots built from an older publish, for the top bar's warning.
"""

from __future__ import annotations

import bpy

from ..core.project import Project
from ..core.updates import Change, changed, publish_version, stale_build
from .identity import built_from
from .libraries import linked_publishes

# The publishes this file links, and their versions when it was opened (or last updated).
seen: dict[str, int | None] = {}


def remember_versions(project: Project) -> None:
    """Note the version of every linked publish, to tell later what's changed."""
    seen.clear()
    seen.update({path: publish_version(project, path) for path in linked_publishes(project)})


def reload_changed(project: Project) -> list[Change]:
    """Reload linked publishes that have been published again since they were seen."""
    libraries = linked_publishes(project)
    for path in [path for path in seen if path not in libraries]:
        del seen[path]  # No longer linked.
    for path in libraries.keys() - seen.keys():
        # Linked since the file opened (from the Asset Browser, say). It may have been
        # published again since it was linked, so reload it to be sure.
        libraries[path].reload()
        seen[path] = publish_version(project, path)
    changes = changed(project, seen)
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


def stale_warning(changes: list[Change]) -> str:
    """What to tell the artist about roots built from an older publish."""
    publishes = ", ".join(f"{change.name} ({change.versions})" for change in changes)
    return (
        f"Published again since this file was built from it: {publishes}. "
        "Materials update when you publish; bring other changes across by hand."
    )
