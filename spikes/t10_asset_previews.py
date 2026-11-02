"""T10: can a publish give the hero's asset a preview, headless?

Run:
    blender -b --factory-startup --python-exit-code 1 --python spikes/t10_asset_previews.py -- --out /tmp/t10

Pass: the hero's asset has a preview showing the asset, readable when linked. The previews
are also saved as PNGs in --out to look at. Also checks the fallback: loading a rendered
image as a custom preview.
If generation fails, render a preview image at publish and load it as the asset's preview.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from spike_utils import (  # noqa: E402
    CHARACTER,
    Checks,
    build_character,
    load_collection,
    open_file,
    output_dir,
    start_file,
    step,
)


def preview_pixels(datablock: bpy.types.ID) -> np.ndarray:
    preview = datablock.preview
    if preview is None or preview.image_size[0] == 0:
        return np.zeros((0, 0, 4), dtype=np.float32)
    width, height = preview.image_size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    preview.image_pixels_float.foreach_get(pixels)
    return pixels.reshape(height, width, 4)


def shows_something(pixels: np.ndarray) -> tuple[bool, str]:
    """True when part of the preview is covered and part isn't: an object, not a blank."""
    if pixels.size == 0:
        return False, "no preview"
    covered = float((pixels[..., 3] > 0.5).mean())
    height, width = pixels.shape[:2]
    return 0.02 < covered < 0.98, f"{width}x{height}, {covered:.0%} covered"


def save_png(pixels: np.ndarray, path: Path) -> None:
    height, width = pixels.shape[:2]
    image = bpy.data.images.new(path.stem, width, height, alpha=True)
    image.pixels.foreach_set(pixels.ravel())
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def render_preview_image(collection: bpy.types.Collection, path: Path) -> None:
    """The fallback: render the asset to a PNG with a temporary camera."""
    scene = bpy.context.scene
    camera = bpy.data.objects.new("preview_cam", bpy.data.cameras.new("preview_cam"))
    camera.data.type, camera.data.ortho_scale = "ORTHO", 4.0
    camera.location, camera.rotation_euler = (0, -6, 1.5), (1.5708, 0, 0)
    scene.collection.objects.link(camera)
    scene.camera = camera
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 4
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(camera)


def main() -> None:
    out = output_dir()
    checks = Checks("T10")
    folder = out / "assets/character/char/rigging"
    hero = folder / "publish/char_rigging.blend"

    step("Generate a preview while publishing, headless")
    collection = build_character(folder / "work/char_rigging_v001.blend")
    collection.asset_mark()
    collection.asset_generate_preview()
    hero.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(hero), {collection}, path_remap="RELATIVE_ALL")
    collection.asset_clear()

    step("Open the hero and check the preview")
    open_file(hero)
    pixels = preview_pixels(bpy.data.collections[CHARACTER])
    ok, detail = shows_something(pixels)
    checks.check("generated preview shows the asset", ok, detail)
    if pixels.size:
        save_png(pixels, out / "preview_generated.png")

    step("Link the hero into a shot and read the preview from the library")
    start_file(out / "shots/010_010_0010/animation/work/010_010_0010_animation_v001.blend")
    ok, detail = shows_something(preview_pixels(load_collection(hero, CHARACTER)))
    checks.check("preview readable on linked data", ok, detail)

    step("Fallback: render an image and load it as a custom preview")
    collection = build_character(folder / "work/char_rigging_v002.blend")
    collection.asset_mark()
    image = out / "preview_render.png"
    render_preview_image(collection, image)
    with bpy.context.temp_override(id=collection):
        bpy.ops.ed.lib_id_load_custom_preview(filepath=str(image))
    ok, detail = shows_something(preview_pixels(collection))
    checks.check("custom preview loads", ok, detail)

    checks.finish()


main()
