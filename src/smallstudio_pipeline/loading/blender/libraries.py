"""Libraries: loading from publishes, what a file links, and the Asset Browser library.

load() links or appends datablocks by name. It is the one place bpy.data.libraries.load
is called, since its type stubs are wrong and it fills lists in place. linked_publishes()
maps a file's libraries to the publishes they are; register_asset_library() adds a
project's assets folder to Blender's asset libraries, linking by default.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import bpy

from ...common.errors import PipelineError
from ...project.core.project import Project
from ...publishing.core.publishing import relative


def load(path: Path, kind: str, names: Iterable[str], link: bool, **options: Any) -> dict[str, Any]:
    """Link or append datablocks of one kind by name.

    kind is a bpy.data collection's name ("collections", "objects", "materials"…). Returns
    {name asked for: datablock}, leaving out names the file doesn't have. The datablock's
    own name can differ: appending next to a local "skin" gives "skin.001".
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


def load_root(path: Path, asset: str, link: bool, **options: Any) -> bpy.types.Collection:
    """Link or append an asset's root collection from one of its publishes."""
    found = load(path, "collections", [asset], link=link, **options)
    if asset not in found:
        raise PipelineError(
            f"{path.name} has no collection called {asset}, so it can't be loaded. "
            "Publish the asset again from its workfile."
        )
    return found[asset]


def linked_publishes(project: Project) -> dict[str, bpy.types.Library]:
    """The libraries this file links from inside the project, by path relative to it."""
    found = {}
    for library in bpy.data.libraries:
        path = Path(bpy.path.abspath(library.filepath)).resolve()
        if path.is_relative_to(project.root):
            found[relative(project, path)] = library
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
