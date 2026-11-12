"""Building a sequence's lighting file from its animation publish.

build_lighting() makes the scene on show the sequence's lighting cut and adds, per shot in
cut order, a lighting scene with a strip in the cut and a comp scene beside it.

A shot's lighting scene holds its light node ("010_010_0010.light"), and inside it the
shot's animation node linked from the animation publish, not overridden: characters,
props, camera and dressed set as animation published them. Per-shot lights go in the
light node. Every lighting scene also links the sequence's light rig ("010_010.lightrig",
one collection, so a change to it shows in every shot) and uses the sequence's world,
where per-shot shader controls live (spike T11).

A shot's comp scene ("010_010_0010.comp") has no objects: its compositor reads the shot's
rendered EXRs through an Image node and runs them through the sequence's comp group
("010_010.comp"), so editing the group changes every shot (spike T7).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import bpy

from ...animation.blender.build import in_cut
from ...common.errors import PipelineError
from ...loading.blender import libraries
from ...project.blender import nodes
from ...project.blender.identity import SHOT
from ...project.blender.nodes import ANIM, LIGHT
from ...project.core.entities import Sequence, Shot
from ...shots.blender import layout


def build_lighting(master: bpy.types.Scene, sequence: Sequence) -> bpy.types.Collection:
    """Make master the sequence's lighting cut, with a lighting and comp scene per shot."""
    publish = sequence.hero_path(ANIM)
    if not publish.exists():
        raise PipelineError(
            f"{sequence.name} has no animation publish. Publish its animation first (even "
            "before anything's animated): lighting links its shots from it."
        )
    shots = in_cut(sequence)
    if not shots:
        raise PipelineError(
            f"{sequence.name}'s layout publish has no shots in its cut. Add shots in layout "
            "and publish it."
        )
    root = layout.start_cut(master, sequence, LIGHT)
    rig = light_rig(sequence)
    world = sequence_world(sequence)
    master.world = world
    group = comp_group(sequence)
    for shot in shots:
        assert shot.metadata.cut_in is not None  # in_cut only keeps shots in the cut.
        scene = lighting_scene(shot, master, publish, rig, world)
        layout.add_strip(master, scene, shot.metadata.cut_in)
        comp_scene(shot, scene, group)
    layout.fit_master_range(master)
    layout.sync_markers(master, sequence)
    return root


def light_rig(sequence: Sequence) -> bpy.types.Collection:
    """The sequence's light rig: one collection every lighting scene links, with a key light."""
    rig = bpy.data.collections.new(f"{sequence.name}.lightrig")
    key = bpy.data.objects.new(f"{sequence.name}_key", bpy.data.lights.new("key", "SUN"))
    key.rotation_euler = (0.8, 0.0, 0.6)
    rig.objects.link(key)
    return rig


def sequence_world(sequence: Sequence) -> bpy.types.World:
    """The sequence's world, shared by every shot: sequence defaults for shader controls."""
    return bpy.data.worlds.new(f"{sequence.name}.world")


def comp_group(sequence: Sequence) -> bpy.types.NodeTree:
    """The sequence's comp group: every shot's comp runs through it. Image in, Image out."""
    group = bpy.data.node_groups.new(f"{sequence.name}.comp", "CompositorNodeTree")
    image_socket(group, "INPUT")
    image_socket(group, "OUTPUT")
    group_in = group.nodes.new("NodeGroupInput")
    group_out = group.nodes.new("NodeGroupOutput")
    group_out.location.x = 300
    group.links.new(group_in.outputs["Image"], group_out.inputs["Image"])
    return group


def lighting_scene(
    shot: Shot,
    master: bpy.types.Scene,
    publish: Path,
    rig: bpy.types.Collection,
    world: bpy.types.World,
) -> bpy.types.Scene:
    """A shot's lighting scene: its light node holding the shot's animation, linked."""
    assert shot.frame_range is not None  # in_cut only keeps shots with a range.
    scene = layout.shot_scene(shot.name, master)
    scene.frame_start, scene.frame_end = shot.frame_range
    scene.world = world
    root = nodes.create_node(scene, f"{shot.name}.{LIGHT}", SHOT, shot.name, LIGHT)
    name = f"{shot.name}.{ANIM}"
    found = libraries.load(publish, "collections", [name], link=True)
    if name not in found:
        raise PipelineError(
            f"{publish.name} has no animation for shot {shot.name}. Publish the animation "
            "again (after Check Updates in the animation file)."
        )
    root.children.link(found[name])
    scene.collection.children.link(rig)
    scene.camera = next((o for o in found[name].all_objects if o.type == "CAMERA"), None)
    nodes.make_active(scene, root)
    return scene


def comp_scene(shot: Shot, lit: bpy.types.Scene, group: bpy.types.NodeTree) -> bpy.types.Scene:
    """A shot's comp scene: no objects, its compositor reading the shot's renders through
    the sequence's comp group. Which renders it reads is set on saving."""
    scene = bpy.data.scenes.new(f"{shot.name}.comp")
    scene.frame_start, scene.frame_end = lit.frame_start, lit.frame_end
    scene.render.fps, scene.render.fps_base = lit.render.fps, lit.render.fps_base
    scene.render.resolution_x = lit.render.resolution_x
    scene.render.resolution_y = lit.render.resolution_y
    scene.render.resolution_percentage = lit.render.resolution_percentage
    tree = bpy.data.node_groups.new(f"{shot.name}.comp", "CompositorNodeTree")
    image_socket(tree, "OUTPUT")
    reader = tree.nodes.new("CompositorNodeImage")
    reader.name = "renders"
    grade: Any = tree.nodes.new("CompositorNodeGroup")  # The stubs miss node_tree.
    grade.node_tree = group
    grade.location.x = 300
    out = tree.nodes.new("NodeGroupOutput")
    out.location.x = 600
    tree.links.new(reader.outputs["Image"], grade.inputs["Image"])
    tree.links.new(grade.outputs["Image"], out.inputs["Image"])
    # Compositor effects are new in 5.3, so the 5.2 stubs don't have them.
    effects: Any = scene.compositor_effects  # pyright: ignore[reportAttributeAccessIssue]
    effects.new("comp").node_group = tree
    scene.render.use_compositing = True
    return scene


def image_socket(tree: bpy.types.NodeTree, in_out: str) -> None:
    """Give a compositor tree an Image input or output."""
    interface: Any = tree.interface  # The stubs only allow socket_type "DEFAULT".
    interface.new_socket("Image", in_out=in_out, socket_type="NodeSocketColor")
