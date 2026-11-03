"""Working on an asset inside another asset's file, such as a prop in its set.

make_editable() swaps a linked asset for a plain local copy where it was, remembering the
placement on the copy's root. When it's published, in_asset_space() moves it back into
the asset's own space for the write, save_asset_workfile() saves it as the asset's next
workfile, and swap_for_link() links the new publish back in where the copy was. Tested as
spike T12.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import bpy
from mathutils import Matrix

from ...core.config import Config
from ...core.entities import Asset
from ...core.errors import PipelineError
from ...core.project import Project
from ...core.publishing import relative
from ...core.updates import publish_version
from .. import libraries, updates
from ..identity import asset_identity, linked_asset

# Where the linked asset was placed, kept on the copy's root while it's being edited.
PLACEMENT = "pipeline_placement"  # The placing empty's world matrix, 16 numbers by row.
PLACEMENT_NAME = "pipeline_placement_name"  # The empty's name, to place the link again.


def make_editable(
    empty: bpy.types.Object, project: Project, view_layer: bpy.types.ViewLayer
) -> bpy.types.Collection:
    """Swap the linked asset an empty instances for a local copy, in the same place."""
    linked = linked_asset(empty)
    identity = asset_identity(linked) if linked else None
    if identity is None:
        raise PipelineError("Select the empty that places a linked asset.")
    asset = project.asset(identity[0])
    task = asset.tasks[0]  # Editing in place is that first task's work.
    version = asset.latest_publish_version(task)
    if version is None:
        raise PipelineError(f"{asset.name} has no {task} publish to edit.")
    # The versioned copy, not the hero: this file links the hero, and Blender won't
    # append cleanly from a file it already links.
    source = asset.publish_path(task, version)
    root = libraries.load_root(source, asset.name, link=False)
    for collection in empty.users_collection:
        collection.children.link(root)

    placement = empty.matrix_world.copy()
    for obj in top_objects(root):
        obj.matrix_basis = placement @ world_matrix(obj, view_layer)
    root[PLACEMENT] = [value for row in placement for value in row]
    root[PLACEMENT_NAME] = empty.name
    bpy.data.objects.remove(empty)
    return root


def top_objects(root: bpy.types.Collection) -> list[bpy.types.Object]:
    """The root's objects whose parent isn't in the root (or that have none)."""
    inside = set(root.all_objects)
    return [obj for obj in root.all_objects if obj.parent not in inside]


def placement_of(root: bpy.types.Collection) -> Matrix | None:
    """Where a made-editable copy was placed, or None for an asset started here."""
    values = root.get(PLACEMENT)
    if values is None:
        return None
    values = list(values)
    return Matrix([values[row * 4 : row * 4 + 4] for row in range(4)])


@contextmanager
def in_asset_space(root: bpy.types.Collection, view_layer: bpy.types.ViewLayer) -> Iterator[None]:
    """Move the root's objects into the asset's own space for as long as this lasts.

    Objects added while editing in place are moved too.
    """
    placement = placement_of(root)
    if placement is None:  # Started here: the file's space is the asset's own.
        yield
        return
    to_asset = placement.inverted()
    saved = [(obj, obj.parent, obj.matrix_basis.copy()) for obj in top_objects(root)]
    try:
        for obj, _, _ in saved:
            world = world_matrix(obj, view_layer)
            obj.parent = None
            obj.matrix_basis = to_asset @ world
        view_layer.update()
        yield
    finally:
        for obj, parent, basis in saved:
            obj.parent = parent
            obj.matrix_basis = basis
        view_layer.update()


def world_matrix(obj: bpy.types.Object, view_layer: bpy.types.ViewLayer) -> Matrix:
    """An object's world matrix, worked out fresh.

    matrix_world is stale until Blender next updates (just after appending or moving
    something, say), so it isn't trusted as it is.
    """
    if obj.parent is None:
        return obj.matrix_basis.copy()
    view_layer.update()
    return obj.matrix_world.copy()


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
    root: bpy.types.Collection, asset: Asset, hero: Path, scene: bpy.types.Scene
) -> bpy.types.Object:
    """Replace the local copy with its published hero, instanced where the copy was placed."""
    homes = [c for c in scene.collection.children_recursive if root in c.children[:]]
    home = homes[0] if homes else scene.collection
    placement = placement_of(root)
    name = root.get(PLACEMENT_NAME, asset.name)

    # Remove the copy and the data only it used, so the next copy doesn't get .001 names.
    objects = list(root.all_objects)
    data = {obj.data for obj in objects if obj.data is not None}
    materials = {slot.material for obj in objects for slot in obj.material_slots if slot.material}
    bpy.data.batch_remove([*objects, *root.children_recursive, root])
    bpy.data.batch_remove([d for d in data if d.users == 0])
    bpy.data.batch_remove([m for m in materials if m.users == 0])

    # The old version is still loaded here (that's what was made editable), and linking
    # again would just hand it back: reload it, so every instance shows the new publish.
    path = relative(asset.project, hero)
    library = libraries.linked_publishes(asset.project).get(path)
    if library is not None:
        library.reload()
    linked = libraries.load_root(hero, asset.name, link=True)
    updates.seen[path] = publish_version(asset.project, path)
    empty = bpy.data.objects.new(name, None)
    home.objects.link(empty)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = linked
    if placement is not None:
        empty.matrix_world = placement
    return empty
