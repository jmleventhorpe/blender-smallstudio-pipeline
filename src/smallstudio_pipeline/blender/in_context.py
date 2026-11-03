"""Working on an asset inside another asset's file, such as a prop in its set.

Make Editable swaps a linked asset for a local copy, keeping the empty that placed it as
a parent (spike T5). Publishing the copy moves it into the asset's own space for the
moment of writing, saves it as the asset's next workfile, publishes it, and swaps it back
for a link on the same empty.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import bpy

from ..core.config import Config
from ..core.entities import Asset, Project
from ..core.errors import PipelineError
from . import libraries
from .identity import asset_identity


def linked_asset(obj: bpy.types.Object | None) -> bpy.types.Collection | None:
    """The linked asset root an empty instances, if it is one."""
    if obj is None or obj.instance_type != "COLLECTION" or obj.instance_collection is None:
        return None
    collection = obj.instance_collection
    return collection if collection.library and asset_identity(collection) else None


def make_editable(placement: bpy.types.Object, project: Project) -> bpy.types.Collection:
    """Swap the linked asset an empty instances for a local copy, in the same place."""
    linked = linked_asset(placement)
    identity = asset_identity(linked) if linked else None
    if identity is None:
        raise PipelineError("Select the empty that places a linked asset.")
    asset = project.asset(identity[0])
    hero = asset.hero_path(asset.tasks[0])  # Editing in place is that first task's work.
    found = libraries.load(hero, "collections", [asset.name], link=False, clear_asset_data=True)
    root = found[asset.name]
    for collection in placement.users_collection:
        collection.children.link(root)
    # The empty stops instancing and becomes the copy's parent, so it stays where it was.
    for obj in top_objects(root):
        obj.parent = placement
    placement.instance_type = "NONE"
    placement.instance_collection = None
    return root


def top_objects(root: bpy.types.Collection) -> list[bpy.types.Object]:
    """The root's objects whose parent isn't in the root (or that have none)."""
    inside = set(root.all_objects)
    return [obj for obj in root.all_objects if obj.parent not in inside]


def placement_of(root: bpy.types.Collection) -> bpy.types.Object | None:
    """The empty a made-editable copy hangs from, if it has one."""
    parents = {obj.parent for obj in top_objects(root)} - {None}
    return parents.pop() if len(parents) == 1 else None


@contextmanager
def in_asset_space(root: bpy.types.Collection) -> Iterator[None]:
    """Move the root's objects into the asset's own space for as long as this lasts:
    unparented from the empty placing them, and objects added in place converted too."""
    placement = placement_of(root)
    to_asset = placement.matrix_world.inverted() if placement else None
    saved = [(obj, obj.parent, obj.matrix_world.copy()) for obj in top_objects(root)]
    try:
        for obj, parent, world in saved:
            if parent is not None:
                obj.parent = None  # Keeps its local transform: its place in the asset.
            elif to_asset is not None:
                obj.matrix_world = to_asset @ world  # Added in place: bring it in too.
        bpy.context.view_layer.update()
        yield
    finally:
        for obj, parent, world in saved:
            obj.parent = parent
            obj.matrix_world = world
        bpy.context.view_layer.update()


# Run in a separate Blender: libraries.write can't write scenes (Blender 5.2 crashes), so
# the root is written on its own and a fresh Blender builds the workfile around it.
_BUILD_WORKFILE = """
import json, sys
import bpy
args = json.loads(sys.argv[sys.argv.index("--") + 1])
bpy.ops.wm.read_homefile(use_empty=True)
with bpy.data.libraries.load(args["source"], link=False) as (_, data_to):
    data_to.collections = [args["root"]]
scene = bpy.context.scene
scene.collection.children.link(data_to.collections[0])
scene.render.fps, scene.render.fps_base = args["fps"], 1.0
scene.render.resolution_x, scene.render.resolution_y = args["resolution"]
scene.render.resolution_percentage = 100
bpy.ops.wm.save_as_mainfile(filepath=args["path"])
"""


def save_asset_workfile(root: bpy.types.Collection, path: Path, config: Config) -> None:
    """Save the root, in a scene of its own, as one of the asset's workfiles."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Beside the workfile, so relative paths inside it stay right.
    temp = path.with_name(f".{path.stem}.root.blend")
    bpy.data.libraries.write(str(temp), {root}, path_remap="RELATIVE_ALL")
    args = {
        "source": str(temp),
        "root": root.name,
        "path": str(path),
        "fps": config.fps,
        "resolution": list(config.resolution),
    }
    command = [bpy.app.binary_path, "-b", "--factory-startup", "--python-exit-code", "1"]
    command += ["--python-expr", _BUILD_WORKFILE, "--", json.dumps(args)]
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as error:
        details = (error.stderr or error.stdout).strip().splitlines()[-1:]
        raise PipelineError(f"Couldn't save {path.name}: {' '.join(details)}") from None
    finally:
        temp.unlink(missing_ok=True)


def swap_for_link(
    root: bpy.types.Collection, asset: Asset, hero: Path, placement: bpy.types.Object | None
) -> bpy.types.Object:
    """Replace the local copy with its published hero, instanced by the same empty."""
    homes = [c for c in bpy.context.scene.collection.children_recursive if root in c.children[:]]
    home = homes[0] if homes else bpy.context.scene.collection
    for obj in list(root.all_objects):
        bpy.data.objects.remove(obj)
    for child in list(root.children_recursive):
        bpy.data.collections.remove(child)
    bpy.data.collections.remove(root)

    linked = libraries.load(hero, "collections", [asset.name], link=True)[asset.name]
    if placement is None:  # Built here from scratch: place it where it was built.
        placement = bpy.data.objects.new(asset.name, None)
        home.objects.link(placement)
    placement.instance_type = "COLLECTION"
    placement.instance_collection = linked
    return placement
