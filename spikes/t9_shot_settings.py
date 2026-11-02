"""T9: can per-shot property overrides on linked data be re-applied, including on a farm?

Run:
    blender -b --factory-startup --python-exit-code 1 --python spikes/t9_shot_settings.py -- --out /tmp/t9

Settings are a list of property paths and values: a sequence-level JSON file next to the
lighting workfiles, plus a text datablock per shot in the lighting file (shot wins). A text
module in the lighting file applies them on load and before each render.

Three shots render a character with an emission material:
    010_010_0010  sequence settings only    -> red
    010_010_0020  shot sets the material    -> green (material is shared by every shot)
    010_010_0030  shot hides the body       -> black

Pass: each shot renders as above in a fresh Blender (as a farm would), and rendering every
shot in one session shows no leftovers from the previous shot.
If it fails, lighting uses library overrides on characters, accepting the name clashes.
"""

import json
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
MATERIAL = "char_skin"
COLOR_PATH = 'node_tree.nodes["Emission"].inputs["Color"].default_value'
RED, GREEN, WHITE, BLACK = (1, 0, 0), (0, 1, 0), (1, 1, 1), (0, 0, 0)

SEQUENCE_SETTINGS = [
    {"material": MATERIAL, "path": COLOR_PATH, "value": [1, 0, 0, 1]},
]
SHOT_SETTINGS = {
    "010_010_0020": [{"material": MATERIAL, "path": COLOR_PATH, "value": [0, 1, 0, 1]}],
    "010_010_0030": [{"object": f"{CHARACTER}_body", "path": "visible_camera", "value": False}],
}

# The applier lives in the lighting file as a text module, so a farm render runs it
# without the add-on (it needs auto-run scripts allowed). The tool would ship it instead.
APPLIER = '''
import json
import bpy
from bpy.app.handlers import persistent

SEQUENCE_FILE = "//../010_010.settings.json"
_originals = {}


def _entries(scene):
    """Sequence entries, then the scene's shot entries, so the shot wins."""
    with open(bpy.path.abspath(SEQUENCE_FILE)) as handle:
        entries = json.load(handle)
    shot = bpy.data.texts.get(scene.name.removesuffix("_lighting") + ".settings.json")
    return entries + (json.loads(shot.as_string()) if shot else [])


def _all_entries():
    entries = []
    for scene in bpy.data.scenes:
        entries += _entries(scene)
    return entries


def _targets(scene, entry):
    if "material" in entry:
        return [m for m in bpy.data.materials if m.name == entry["material"]]
    # Objects are looked up in this shot's scene only; names repeat across shots.
    return [o for o in scene.objects if o.name.split(".")[0] == entry["object"]]


def _set(datablock, path, value):
    parent_path, _, attribute = path.rpartition(".")
    parent = datablock.path_resolve(parent_path) if parent_path else datablock
    if not _originals.get((datablock.session_uid, path)):
        current = getattr(parent, attribute)
        _originals[(datablock.session_uid, path)] = (parent, attribute, current[:] if hasattr(current, "__len__") else current)
    setattr(parent, attribute, value)


def apply(scene):
    """Reset everything any shot touches, then apply sequence and shot settings."""
    for scene_ in bpy.data.scenes:
        for entry in _entries(scene_):
            for target in _targets(scene_, entry):
                key = (target.session_uid, entry["path"])
                if key in _originals:
                    parent, attribute, value = _originals[key]
                    setattr(parent, attribute, value)
    for entry in _entries(scene):
        for target in _targets(scene, entry):
            _set(target, entry["path"], entry["value"])
    print(f"T9 APPLIED settings for {scene.name}")


@persistent
def _on_load(_):
    apply(bpy.context.scene)


@persistent
def _on_render(scene, _=None):
    apply(scene)


bpy.app.handlers.load_post.append(_on_load)
bpy.app.handlers.render_pre.append(_on_render)
'''


def build_rig(path: Path) -> Path:
    """The usual character, with an emission material so render colours read exactly."""
    collection = build_character(path)
    material = bpy.data.materials.new(MATERIAL)
    nodes = material.node_tree.nodes
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    emission.name = "Emission"
    emission.inputs["Color"].default_value = (1, 1, 1, 1)
    output = nodes.new("ShaderNodeOutputMaterial")
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
    folder = out / "sequences/010_010/lighting"
    path = folder / "work/010_010_lighting_v001.blend"
    start_file(path)
    for index, (shot, publish) in enumerate(publishes.items()):
        scene = bpy.context.scene if index == 0 else bpy.data.scenes.new("shot")
        scene.name = f"{shot}_lighting"
        scene.collection.children.link(load_collection(publish, OUTPUT))
        # An orthographic camera looking at the middle of the body, from the front.
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

    (folder / "010_010.settings.json").write_text(json.dumps(SEQUENCE_SETTINGS, indent=2))
    for shot, entries in SHOT_SETTINGS.items():
        bpy.data.texts.new(f"{shot}.settings.json").write(json.dumps(entries, indent=2))
    applier = bpy.data.texts.new("pipeline_shot_settings.py")
    applier.write(APPLIER)
    applier.use_module = True  # Runs on load when auto-run scripts are allowed.
    bpy.ops.wm.save_mainfile()
    return path


def render(path: Path, scenes: list[str], autoexec: bool) -> str:
    """Render frame 1 of each scene in one fresh Blender, as a farm job would."""
    code = "; ".join(f"bpy.ops.render.render(write_still=True, scene='{s}')" for s in scenes)
    args = [bpy.app.binary_path, "-b", "--factory-startup"]
    args += ["-y"] if autoexec else ["-Y"]
    args += [str(path), "--python-expr", f"import bpy; {code}"]
    done = subprocess.run(args, capture_output=True, text=True, check=True)
    return done.stdout


def centre_colour(out: Path, shot: str) -> tuple[float, float, float]:
    path = next(render_path(out, shot).parent.glob("*.exr"))
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = image.size
    index = ((height // 2) * width + width // 2) * 4
    colour = tuple(round(v, 2) for v in image.pixels[index : index + 3])
    bpy.data.images.remove(image)
    path.unlink()
    return colour


def same(colour: tuple[float, ...], expected: tuple[int, ...]) -> bool:
    return all(abs(c - e) < 0.1 for c, e in zip(colour, expected, strict=True))


def main() -> None:
    out = output_dir()
    checks = Checks("T9")
    expected = {"010_010_0010": RED, "010_010_0020": GREEN, "010_010_0030": BLACK}

    step("Build the rig with an emission material, and an animation publish per shot")
    rig_hero = build_rig(out / "assets/character/char/rigging/work/char_rigging_v001.blend")
    publishes = {shot: publish_animation(out, shot, rig_hero) for shot in SHOTS}

    step("Build the sequence lighting file with sequence and shot settings")
    lighting = build_lighting(out, publishes)

    step("Farm-style: each shot in its own fresh Blender, auto-run scripts blocked")
    for shot in SHOTS:
        render(lighting, [f"{shot}_lighting"], autoexec=False)
        colour = centre_colour(out, shot)
        checks.check(f"{shot} without the script shows untouched data", same(colour, WHITE), str(colour))

    step("Farm-style: each shot in its own fresh Blender, auto-run scripts allowed")
    for shot in SHOTS:
        log = render(lighting, [f"{shot}_lighting"], autoexec=True)
        colour = centre_colour(out, shot)
        applied = f"T9 APPLIED settings for {shot}_lighting" in log
        checks.check(f"{shot} renders with its settings", same(colour, expected[shot]) and applied, str(colour))

    step("Session-style: all shots in one Blender, green shot first to catch leftovers")
    order = ["010_010_0020", "010_010_0010", "010_010_0030"]
    render(lighting, [f"{shot}_lighting" for shot in order], autoexec=True)
    for shot in order:
        colour = centre_colour(out, shot)
        checks.check(
            f"{shot} correct after other shots rendered", same(colour, expected[shot]), str(colour)
        )

    checks.finish()


main()
