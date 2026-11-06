"""Keeping a file's links current: the Blender side of loading/core/updates.py.

remember_versions() notes, when a file opens, the version of every publish it links;
reload_changed() (Check Updates) reloads the ones published again since.
"""

from __future__ import annotations

from ...project.core.project import Project
from ..core.updates import Change, changed, publish_version
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
