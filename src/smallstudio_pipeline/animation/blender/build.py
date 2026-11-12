"""Building a sequence's animation file from its layout publish (spike T14).

build_animation() makes the scene on show the sequence's animation cut and adds a scene
per shot, in cut order, with a strip at the shot's place in the cut. Each shot's scene
holds its animation node ("010_010_0010.anim"), and inside it the shot's node linked from
the layout publish and overridden: its camera, cast and dressed set, as layout left
them. Nothing is copied, so a republished layout comes through on opening, for anything
the animator hasn't changed.

Shots come from the shots' metadata, which layout publishes write: those with a frame
range and a place in the cut, and not omitted. sync_with_layout() (Check Updates) brings
the cut in line with the latest layout publish: new shots get a scene, retimed ones their
range and place, and omitted ones lose their strip but keep their scene and its work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import bpy

from ...common.errors import PipelineError
from ...loading.blender import libraries
from ...project.blender import nodes
from ...project.blender.identity import SHOT
from ...project.blender.nodes import ANIM
from ...project.core.entities import Sequence, Shot
from ...shots.blender import layout


def build_animation(master: bpy.types.Scene, sequence: Sequence) -> bpy.types.Collection:
    """Make master the sequence's animation cut, with a scene per shot from its layout."""
    publish = sequence.hero_path(layout.LAYOUT)
    if not publish.exists():
        raise PipelineError(
            f"{sequence.name} has no layout publish. Publish its layout first: animation "
            "links its shots from it."
        )
    shots = in_cut(sequence)
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


@dataclass
class Sync:
    """What sync_with_layout() changed, by shot code."""

    added: list[str] = field(default_factory=list)
    retimed: list[str] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """e.g. "added 0030; retimed 0010", or "" if nothing changed."""
        parts = [
            f"{label} {', '.join(layout.shot_number(code) for code in codes)}"
            for label, codes in (
                ("added", self.added),
                ("retimed", self.retimed),
                ("omitted", self.omitted),
            )
            if codes
        ]
        return "; ".join(parts)


def sync_with_layout(master: bpy.types.Scene, sequence: Sequence) -> Sync:
    """Make the animation cut the latest layout publish's: its shots, ranges and places."""
    publish = sequence.hero_path(layout.LAYOUT)
    scenes = {node.name: scene for scene in bpy.data.scenes if (node := nodes.shot_node(scene))}
    editor = master.sequence_editor
    assert editor is not None  # A master scene always has one (layout.start_cut).
    before = {}
    for strip in layout.shot_strips(master):
        shown = strip.scene
        assert shown is not None  # shot_strips only returns strips showing a shot.
        before[layout.strip_shot(strip)] = (strip.left_handle, shown.frame_start, shown.frame_end)
        editor.strips.remove(strip)

    sync = Sync()
    for shot in in_cut(sequence):
        assert shot.frame_range is not None and shot.metadata.cut_in is not None  # in_cut.
        scene = scenes.get(shot.name)
        if scene is None:
            scene = shot_scene(shot, master, publish)
            sync.added.append(shot.name)
        scene.frame_start, scene.frame_end = shot.frame_range
        layout.add_strip(master, scene, shot.metadata.cut_in)
        now = (shot.metadata.cut_in, *shot.frame_range)
        if shot.name in before and before[shot.name] != now:
            sync.retimed.append(shot.name)
    kept = {layout.strip_shot(strip) for strip in layout.shot_strips(master)}
    sync.omitted = sorted(code for code in before if code not in kept)
    layout.fit_master_range(master)
    layout.sync_markers(master, sequence)
    return sync


def in_cut(sequence: Sequence) -> list[Shot]:
    """The sequence's shots in its last layout publish's cut, in cut order."""
    shots = [
        shot
        for shot in sequence.shots()
        if shot.frame_range is not None and shot.metadata.cut_in is not None
    ]
    return sorted(shots, key=lambda shot: shot.metadata.cut_in or 0)


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
