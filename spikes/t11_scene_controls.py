"""T11: can one shared, linked material render different values per shot, with no scripts?

Run:
    blender -b --factory-startup --python-exit-code 1 --python spikes/t11_scene_controls.py -- --out /tmp/t11

The character's material reads its tint through an Attribute node of type View Layer,
which looks the name up on the view layer, then the scene, then the world. The lighting
file sets values as plain custom properties, saved like any local data:

    010_010_0010  nothing set; the shared sequence world says red  -> red
    010_010_0020  its scene says green                             -> green
    010_010_0030  its view layer says blue                         -> blue

Pass: each shot renders its colour in Cycles and EEVEE, with auto-run scripts blocked,
both one shot per fresh Blender and all shots in one session.
If it fails, per-shot shader tweaks fall back to the T9 settings script.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bpy  # noqa: E402
from spike_utils import (  # noqa: E402
    CHARACTER,
    OUTPUT,
    Checks,
    build_animation,
    build_character,
    load_collection,
    output_dir,
    start_file,
    step,
    write_publish,
)

SHOTS = ["010_010_0010", "010_010_0020", "010_010_0030"]
CONTROL = "char_tint"
EXPECTED = {"010_010_0010": (1, 0, 0), "010_010_0020": (0, 1, 0), "010_010_0030": (0, 0, 1)}


def build_rig(path: Path) -> Path:
    """The usual character, whose emission colour comes from a View Layer attribute."""
    collection = build_character(path)
    material = bpy.data.materials.new("char_skin")
    nodes = material.node_tree.nodes
    nodes.clear()
    control = nodes.new("ShaderNodeAttribute")
    control.attribute_type = "VIEW_LAYER"
    control.attribute_name = CONTROL
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    material.node_tree.links.new(control.outputs["Color"], emission.inputs["Color"])
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    bpy.data.objects[f"{CHARACTER}_body"].data.materials.append(material)
    bpy.ops.wm.save_mainfile()
    hero = path.parent.parent / "publish/char_rigging.blend"
    write_publish(collection, hero, hero.with_name("char_rigging_v001.blend"), mark=[collection])
    return hero


def publish_animation(out: Path, shot: str, rig_hero: Path) -> Path:
    folder = out / f"shots/{shot}/animation"
    build_animation(folder / f"work/{shot}_animation_v001.blend", rig_hero)
    hero = folder / f"publish/{shot}_animation.blend"
    write_publish(bpy.data.collections[OUTPUT], hero, hero.with_name(f"{shot}_animation_v001.blend"))
    return hero


def render_path(out: Path, shot: str) -> Path:
    return out / f"shots/{shot}/lighting/render/v001/{shot}_lighting_"


def build_lighting(out: Path, publishes: dict[str, Path]) -> Path:
    path = out / "sequences/010_010/lighting/work/010_010_lighting_v001.blend"
    start_file(path)
    # One world shared by every shot scene holds the sequence-level values.
    world = bpy.data.worlds.new("seq_world")
    world.color = (0, 0, 0)
    world[CONTROL] = [1.0, 0.0, 0.0]
    for index, (shot, publish) in enumerate(publishes.items()):
        scene = bpy.context.scene if index == 0 else bpy.data.scenes.new("shot")
        scene.name = f"{shot}_lighting"
        scene.world = world
        scene.collection.children.link(load_collection(publish, OUTPUT))
        camera = bpy.data.objects.new(f"cam_{shot}", bpy.data.cameras.new(f"cam_{shot}"))
        camera.data.type, camera.data.ortho_scale = "ORTHO", 1.0
        camera.location, camera.rotation_euler = (0, -6, 0.5), (1.5708, 0, 0)
        scene.collection.objects.link(camera)
        scene.camera = camera
        scene.frame_start = scene.frame_end = 1
        scene.render.engine = "CYCLES"
        scene.cycles.device, scene.cycles.samples = "CPU", 1
        # No pixel filter or denoiser, so colours read exactly.
        scene.cycles.filter_width = 0.01
        scene.cycles.use_denoising = False
        scene.render.resolution_x = scene.render.resolution_y = 16
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "OPEN_EXR"
        scene.render.filepath = str(render_path(out, shot))

    bpy.data.scenes["010_010_0020_lighting"][CONTROL] = [0.0, 1.0, 0.0]
    bpy.data.scenes["010_010_0030_lighting"].view_layers[0][CONTROL] = [0.0, 0.0, 1.0]
    bpy.ops.wm.save_mainfile()
    return path


def render(path: Path, scenes: list[str], engine: str) -> None:
    """Render frame 1 of each scene in one fresh Blender, with auto-run scripts blocked."""
    code = "; ".join(
        f"bpy.data.scenes['{s}'].render.engine = '{engine}'; "
        f"bpy.ops.render.render(write_still=True, scene='{s}')"
        for s in scenes
    )
    args = [bpy.app.binary_path, "-b", "--factory-startup", "-Y", str(path)]
    subprocess.run([*args, "--python-expr", f"import bpy; {code}"], capture_output=True, check=True)


def centre_colour(out: Path, shot: str) -> tuple[float, ...]:
    path = next(render_path(out, shot).parent.glob("*.exr"))
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = image.size
    index = ((height // 2) * width + width // 2) * 4
    colour = tuple(round(v, 2) for v in image.pixels[index : index + 3])
    bpy.data.images.remove(image)
    path.unlink()
    return colour


def same(colour: tuple[float, ...], expected: tuple[int, ...]) -> bool:
    return all(abs(c - e) < 0.01 for c, e in zip(colour, expected, strict=True))


def main() -> None:
    out = output_dir()
    checks = Checks("T11")

    step("Build the rig with a View Layer attribute driving its material, and three shots")
    rig_hero = build_rig(out / "assets/character/char/rigging/work/char_rigging_v001.blend")
    publishes = {shot: publish_animation(out, shot, rig_hero) for shot in SHOTS}

    step("Build the sequence lighting file: world, scene and view layer values")
    lighting = build_lighting(out, publishes)

    for engine in ("CYCLES", "BLENDER_EEVEE"):
        step(f"{engine}: each shot in its own fresh Blender, auto-run scripts blocked")
        for shot in SHOTS:
            render(lighting, [f"{shot}_lighting"], engine)
            colour = centre_colour(out, shot)
            checks.check(f"{shot} renders its value", same(colour, EXPECTED[shot]), str(colour))

        step(f"{engine}: all shots in one session, green shot first")
        order = ["010_010_0020", "010_010_0010", "010_010_0030"]
        render(lighting, [f"{shot}_lighting" for shot in order], engine)
        for shot in order:
            colour = centre_colour(out, shot)
            checks.check(f"{shot} correct after other shots", same(colour, EXPECTED[shot]), str(colour))

    checks.finish()


main()
