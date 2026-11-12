"""Building a sequence's animation file from its layout publish (spike T14).

build_animation() makes the scene on show the sequence's animation cut and adds a scene
per shot, in cut order, with a strip at the shot's place in the cut. Each shot's scene
holds its animation node ("010_010_0010.anim"), and inside it the shot's node linked from
the layout publish and overridden: its camera, cast and dressed set, as layout left
them. Nothing is copied, so a republished layout comes through on opening, for anything
the animator hasn't changed.

Shots come from the shots' metadata, which layout publishes write: those with a frame
range and a place in the cut, and not omitted (shots/blender/follow.py).
sync_with_layout() (Check Updates) brings the cut in line with the latest layout publish.
"""

from __future__ import annotations

from pathlib import Path

import bpy

from ...common.errors import PipelineError
from ...loading.blender import libraries
from ...project.blender import nodes
from ...project.blender.identity import SHOT
from ...project.blender.nodes import ANIM
from ...project.core.entities import Sequence, Shot
from ...shots.blender import follow, layout


def build_animation(master: bpy.types.Scene, sequence: Sequence) -> bpy.types.Collection:
    """Make master the sequence's animation cut, with a scene per shot from its layout."""
    publish = sequence.hero_path(layout.LAYOUT)
    if not publish.exists():
        raise PipelineError(
            f"{sequence.name} has no layout publish. Publish its layout first: animation "
            "links its shots from it."
        )
    shots = follow.in_cut(sequence)
    if not shots:
        raise PipelineError(
            f"{sequence.name}'s layout publish has no shots in its cut. Add shots in layout "
            "and publish it."
        )
    root = layout.start_cut(master, sequence, ANIM)
    for shot in shots:
        assert shot.metadata.cut_in is not None  # in_cut only keeps shots in the cut.
        scene = shot_scene(shot, master, publish)
        layout.add_strip(master, scene, shot.metadata.cut_in)
    layout.fit_master_range(master)
    layout.sync_markers(master, sequence)
    return root


def sync_with_layout(master: bpy.types.Scene, sequence: Sequence) -> follow.Sync:
    """Make the animation cut the latest layout publish's (Check Updates)."""
    publish = sequence.hero_path(layout.LAYOUT)
    return follow.follow_layout(master, sequence, lambda shot: shot_scene(shot, master, publish))


def shot_scene(shot: Shot, master: bpy.types.Scene, publish: Path) -> bpy.types.Scene:
    """A shot's scene: its animation node, holding its layout node linked and overridden."""
    assert shot.frame_range is not None  # in_cut only keeps shots with a range.
    scene = layout.shot_scene(shot.name, master)
    scene.frame_start, scene.frame_end = shot.frame_range
    root = nodes.create_node(scene, f"{shot.name}.{ANIM}", SHOT, shot.name, ANIM)

    found = libraries.load(publish, "collections", [shot.name], link=True)
    if shot.name not in found:
        raise PipelineError(
            f"{publish.name} has no node for shot {shot.name}. Publish the layout again."
        )
    linked = found[shot.name]
    view_layer = scene.view_layers[0]
    if view_layer.layer_collection is None:  # A new scene's, until Blender updates it.
        view_layer.update()
    scene.collection.children.link(linked)
    override = linked.override_hierarchy_create(scene, view_layer, do_fully_editable=True)
    # Blender leaves both in the scene's top collection: the override moves into the node.
    for child in (linked, override):
        if child in scene.collection.children[:]:
            scene.collection.children.unlink(child)
    root.children.link(override)
    nodes.make_active(scene, root)
    scene.camera = next((o for o in override.all_objects if o.type == "CAMERA"), None)
    return scene
