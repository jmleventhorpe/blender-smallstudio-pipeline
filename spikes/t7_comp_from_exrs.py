"""T7: can a comp scene read rendered EXRs and render without the 3D scene?

Run:
    blender -b --factory-startup --python spikes/t7_comp_from_exrs.py -- --out /tmp/t7

Pass: rendering a comp scene runs only the compositor and writes frames; editing the
shared sequence comp group changes every shot's comp.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bmesh
import bpy
import numpy as np

from spike_utils import Checks, output_dir, start_file, step

SHOTS = ["010_010_0010", "010_010_0020"]
FRAMES = (1, 2)
GROUP = "seq_comp"


def render_dir(out: Path, shot: str) -> Path:
    return out / f"shots/{shot}/lighting/render/v001"


def build_lighting_scene(scene: bpy.types.Scene, out: Path, shot: str, energy: float) -> None:
    """A lit cube rendered by Cycles to multilayer EXRs."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    mesh = bpy.data.meshes.new(f"{shot}_cube")
    bm.to_mesh(mesh)
    bm.free()
    cube = bpy.data.objects.new(f"{shot}_cube", mesh)
    sun = bpy.data.objects.new(f"{shot}_sun", bpy.data.lights.new(f"{shot}_sun", "SUN"))
    sun.data.energy = energy
    sun.rotation_euler = (0.6, 0.2, 0.0)
    camera = bpy.data.objects.new(f"{shot}_cam", bpy.data.cameras.new(f"{shot}_cam"))
    camera.location = (4.0, -4.0, 3.0)
    camera.rotation_euler = (1.1, 0.0, 0.8)
    for obj in (cube, sun, camera):
        scene.collection.objects.link(obj)
    scene.camera = camera

    scene.frame_start, scene.frame_end = FRAMES
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 4
    scene.render.resolution_x, scene.render.resolution_y = 64, 36
    scene.render.resolution_percentage = 100
    # Blender 5 picks multilayer through media_type, not file_format.
    scene.render.image_settings.media_type = "MULTI_LAYER_IMAGE"
    scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
    layer = scene.view_layers[0].name
    scene.render.filepath = str(render_dir(out, shot) / layer / f"{shot}_lighting_")


def build_comp_group() -> bpy.types.NodeTree:
    """The shared sequence comp group: Image in, exposure, Image out."""
    group = bpy.data.node_groups.new(GROUP, "CompositorNodeTree")
    group.interface.new_socket("Image", in_out="INPUT", socket_type="NodeSocketColor")
    group.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    group_in = group.nodes.new("NodeGroupInput")
    exposure = group.nodes.new("CompositorNodeExposure")
    exposure.name = "grade"
    exposure.inputs["Exposure"].default_value = 0.0
    group_out = group.nodes.new("NodeGroupOutput")
    group.links.new(group_in.outputs["Image"], exposure.inputs["Image"])
    group.links.new(exposure.outputs["Image"], group_out.inputs["Image"])
    return group


def build_comp_scene(out: Path, shot: str, group: bpy.types.NodeTree) -> bpy.types.Scene:
    """A comp scene with no objects or camera: EXR sequence -> shared group -> output."""
    scene = bpy.data.scenes.new(f"{shot}_comp")
    scene.frame_start, scene.frame_end = FRAMES
    scene.render.resolution_x, scene.render.resolution_y = 64, 36
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.filepath = str(render_dir(out, shot) / "comp" / f"{shot}_comp_")

    first_frame = next((render_dir(out, shot) / "ViewLayer").glob("*_0001.exr"))
    image = bpy.data.images.load(str(first_frame))
    image.source = "SEQUENCE"

    tree = bpy.data.node_groups.new(f"{shot}_comp", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    reader = tree.nodes.new("CompositorNodeImage")
    reader.image = image
    reader.frame_start = FRAMES[0]
    reader.frame_duration = len(range(FRAMES[0], FRAMES[1] + 1))
    print(f"   {shot} image node outputs: {[s.name for s in reader.outputs]}")
    grade = tree.nodes.new("CompositorNodeGroup")
    grade.node_tree = group
    tree_out = tree.nodes.new("NodeGroupOutput")
    # A multilayer EXR shows its passes by name on the Image node.
    tree.links.new(reader.outputs["Combined"], grade.inputs["Image"])
    tree.links.new(grade.outputs["Image"], tree_out.inputs["Image"])

    scene.compositing_node_group = tree
    scene.render.use_compositing = True
    return scene


def render(scene: bpy.types.Scene) -> float:
    start = time.perf_counter()
    bpy.ops.render.render(animation=True, scene=scene.name)
    return time.perf_counter() - start


def mean_brightness(path: Path) -> float:
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(pixels)
    bpy.data.images.remove(image)
    return float(pixels.reshape(-1, 4)[:, :3].mean())


def comp_frames(out: Path, shot: str) -> list[Path]:
    return sorted((render_dir(out, shot) / "comp").glob("*.exr"))


def main() -> None:
    out = output_dir()
    checks = Checks("T7")
    start_file(out / "sequences/010_010/lighting/work/010_010_lighting_v001.blend")

    step("Lighting: render each shot's scene to multilayer EXRs")
    for index, shot in enumerate(SHOTS):
        scene = bpy.context.scene if index == 0 else bpy.data.scenes.new("tmp")
        scene.name = f"{shot}_lighting"
        # A different light level per shot, so each comp can be traced to its own EXRs.
        build_lighting_scene(scene, out, shot, energy=3.0 + 3.0 * index)
        seconds = render(scene)
        exrs = sorted((render_dir(out, shot) / "ViewLayer").glob("*.exr"))
        checks.check(
            f"{shot} lighting wrote EXRs", len(exrs) == 2, f"{len(exrs)} files, {seconds:.2f}s"
        )

    step("Comp: a comp scene per shot feeding the shared group, rendered with no camera")
    group = build_comp_group()
    comp_scenes = {shot: build_comp_scene(out, shot, group) for shot in SHOTS}
    baseline = {}
    for shot, scene in comp_scenes.items():
        try:
            seconds = render(scene)
            rendered, detail = True, f"{seconds:.2f}s"
        except RuntimeError as error:
            rendered, detail = False, str(error)
        checks.check(f"{shot} comp renders with no camera or objects", rendered, detail)
        frames = comp_frames(out, shot)
        checks.check(f"{shot} comp wrote frames", len(frames) == 2, f"{len(frames)} files")
        means = [mean_brightness(frame) for frame in frames]
        baseline[shot] = means[0] if means else 0.0
        checks.check(
            f"{shot} comp reads its EXRs on every frame",
            len(means) == 2 and means[0] > 0.0 and abs(means[0] - means[1]) < 1e-4,
            ", ".join(f"{m:.4f}" for m in means),
        )
    first, second = (baseline[shot] for shot in SHOTS)
    checks.check("each shot's comp reads its own lighting", abs(first - second) > 0.01)

    step("Edit the shared group (one stop down), re-render every comp scene")
    group.nodes["grade"].inputs["Exposure"].default_value = -1.0
    for shot, scene in comp_scenes.items():
        render(scene)
        graded = mean_brightness(comp_frames(out, shot)[0])
        ratio = graded / baseline[shot] if baseline[shot] else 0.0
        checks.check(
            f"{shot} picks up the group edit", abs(ratio - 0.5) < 0.01, f"ratio {ratio:.4f}"
        )

    bpy.ops.wm.save_mainfile()
    checks.finish()


main()
