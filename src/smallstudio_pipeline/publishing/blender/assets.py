"""Writing a publish from the open session: the Blender side of publishing/core/publishing.py.

pick_root() finds the asset root to publish: the innermost one holding the selection, or
the file's only one. write_publish() writes only that root and what it uses (spike T3):
the hero file, marked as an asset that links, with a thumbnail and catalog (T8, T10),
then the versioned copy, unmarked; the artist's session is left as it was. Thumbnails are
a quick Workbench render, falling back to Blender's generator where it can't render.
"""

from __future__ import annotations

import math
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import bpy
from mathutils import Euler, Vector

from ...common.errors import PipelineError
from ...common.files import replace_with_retry
from ...loading.core.updates import publish_version
from ...project.blender.identity import asset_identity
from ...project.core.entities import Asset
from ..core.catalogs import ensure_catalog
from ..core.publishing import Dependency, PublishPlan, relative

THUMBNAIL_SIZE = 256


def asset_roots(scene: bpy.types.Scene) -> list[bpy.types.Collection]:
    """Every asset root collection in the scene."""
    return [c for c in scene.collection.children_recursive if asset_identity(c)]


def pick_root(context: bpy.types.Context) -> bpy.types.Collection:
    """The asset root to publish: the one holding the selection, or the file's only one."""
    roots = asset_roots(context.scene)
    selected = context.selected_objects
    if selected:
        holding = [root for root in roots if any(obj in root.all_objects[:] for obj in selected)]
        # A prop being edited inside its set is in both roots: the innermost one wins.
        holding = [
            root
            for root in holding
            if not any(other in root.children_recursive[:] for other in holding)
        ]
        if len(holding) == 1:
            return holding[0]
        if len(holding) > 1:
            names = ", ".join(root.name for root in holding)
            raise PipelineError(f"The selection is in several assets ({names}). Select one.")
    if len(roots) == 1:
        return roots[0]
    if not roots:
        raise PipelineError("There's no asset in this file to publish.")
    names = ", ".join(root.name for root in roots)
    raise PipelineError(f"This file has several assets ({names}). Select something in one.")


def write_publish(root: bpy.types.Collection, plan: PublishPlan) -> None:
    """Write the hero file (marked as an asset) and the versioned copy (unmarked)."""
    asset = plan.entity
    if not isinstance(asset, Asset):
        raise PipelineError(f"{asset.label} isn't an asset; this writes asset publishes.")
    settings = asset.settings
    library = asset.project.root / asset.project.config.asset_library
    if settings.mark_children:  # A kit: each piece is an asset in the kit's own catalog.
        marked, catalog = list(root.children), f"{asset.asset_type}/{asset.name}"
    else:
        marked, catalog = [root], asset.asset_type
    catalog_id = str(ensure_catalog(library, catalog))

    plan.hero.parent.mkdir(parents=True, exist_ok=True)
    with marked_as_assets(marked, catalog_id):
        # The temp file sits beside the hero so relative paths and the rename both hold.
        temp = plan.hero.with_name(f"{plan.hero.stem}.tmp.blend")
        bpy.data.libraries.write(str(temp), {root}, path_remap="RELATIVE_ALL")
        replace_with_retry(temp, plan.hero)
    bpy.data.libraries.write(str(plan.path), {root}, path_remap="RELATIVE_ALL")


@contextmanager
def marked_as_assets(collections: list[bpy.types.Collection], catalog_id: str) -> Iterator[None]:
    """Mark collections as assets that link, with a thumbnail, then unmark them again."""
    fake_users = {collection: collection.use_fake_user for collection in collections}
    try:
        for collection in collections:
            collection.asset_mark()
            collection.asset_data.catalog_id = catalog_id
            collection.asset_data.use_preferred_import_method = True
            collection.asset_data.preferred_import_method = "LINK"
            add_thumbnail(collection)
        yield
    finally:
        for collection, had_fake_user in fake_users.items():
            collection.asset_clear()
            collection.use_fake_user = had_fake_user


def add_thumbnail(collection: bpy.types.Collection) -> None:
    """Render a thumbnail and use it as the asset's preview.

    Blender's own preview generation runs in the background in the UI, so it may not be
    ready before the hero is written. A quick Workbench render is ready straight away.
    Where it can't render (no GPU), Blender's generator works headless (spike T10).
    """
    with tempfile.TemporaryDirectory() as folder:
        image = Path(folder) / "thumbnail.png"
        try:
            render_thumbnail(collection, image)
        except RuntimeError:
            collection.asset_generate_preview()
            return
        # The stubs miss temp_override's context-manager methods.
        with bpy.context.temp_override(id=collection):  # pyright: ignore[reportGeneralTypeIssues]
            bpy.ops.ed.lib_id_load_custom_preview(filepath=str(image))


def render_thumbnail(collection: bpy.types.Collection, path: Path) -> None:
    """Render the collection with Workbench from a three-quarter view, in a scratch scene."""
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in collection.all_objects
        if obj.type in {"MESH", "CURVE", "SURFACE", "FONT", "GREASEPENCIL"}
        for corner in obj.bound_box
    ]
    if not points:
        raise RuntimeError("Nothing to render.")
    low = Vector([min(p[i] for p in points) for i in range(3)])
    high = Vector([max(p[i] for p in points) for i in range(3)])
    centre, size = (low + high) / 2, max((high - low).length, 0.01)

    scene = bpy.data.scenes.new("pipeline_thumbnail")
    lens = bpy.data.cameras.new("pipeline_thumbnail")
    camera = bpy.data.objects.new("pipeline_thumbnail", lens)
    try:
        scene.collection.children.link(collection)
        scene.collection.objects.link(camera)
        scene.camera = camera
        lens.type, lens.ortho_scale, lens.clip_end = "ORTHO", size * 1.1, size * 5
        camera.rotation_euler = Euler((math.radians(65), 0, math.radians(35)))
        camera.location = centre + camera.rotation_euler.to_matrix() @ Vector((0, 0, size * 2))
        scene.render.engine = "BLENDER_WORKBENCH"  # pyright: ignore[reportAttributeAccessIssue]
        scene.render.film_transparent = True
        scene.render.resolution_x = scene.render.resolution_y = THUMBNAIL_SIZE
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True, scene=scene.name)
    finally:  # Leave nothing behind in the artist's file.
        bpy.data.objects.remove(camera)
        bpy.data.cameras.remove(lens)
        bpy.data.scenes.remove(scene)
    if not path.exists():
        raise RuntimeError("The thumbnail render didn't write an image.")


def dependencies(root: bpy.types.Collection, plan: PublishPlan) -> list[Dependency]:
    """The publishes the asset links (lib pieces in a set, say), with their versions now."""
    project = plan.entity.project
    libraries = set()
    for obj in root.all_objects:
        for data in (obj, obj.data, obj.instance_collection):
            if data is not None and data.library is not None:
                libraries.add(Path(bpy.path.abspath(data.library.filepath)).resolve())
    found = []
    for path in sorted(libraries):
        if path.is_relative_to(project.root):  # Libraries outside the project aren't publishes.
            name = relative(project, path)
            found.append(Dependency(name, publish_version(project, name)))
    return found
