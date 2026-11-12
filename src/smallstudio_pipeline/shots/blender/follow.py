"""Cuts that follow layout's: the animation and lighting files' cuts.

An animation or lighting file's cut is built from the shots' metadata, which layout
publishes write (in_cut): every shot with a frame range and a place in the cut, and not
omitted, in cut order. follow_layout() (Check Updates) brings such a cut in line with the
latest layout publish: new shots get a scene, made by the file's own builder; retimed
ones their range and place; omitted ones lose their strip but keep their scene and its
work. New scenes are made before anything else changes, so a shot that can't be built
leaves the cut as it was.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import bpy

from ...project.blender import nodes
from ...project.core.entities import Sequence, Shot
from . import layout


@dataclass
class Sync:
    """What follow_layout() changed, by shot code."""

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


def in_cut(sequence: Sequence) -> list[Shot]:
    """The sequence's shots in its last layout publish's cut, in cut order."""
    shots = [
        shot
        for shot in sequence.shots()
        if shot.frame_range is not None and shot.metadata.cut_in is not None
    ]
    return sorted(shots, key=lambda shot: shot.metadata.cut_in or 0)


def follow_layout(
    master: bpy.types.Scene,
    sequence: Sequence,
    make_scene: Callable[[Shot], bpy.types.Scene],
) -> Sync:
    """Make master's cut the latest layout publish's: its shots, ranges and places."""
    scenes = {node.name: scene for scene in bpy.data.scenes if (node := nodes.shot_node(scene))}
    shots = in_cut(sequence)
    sync = Sync()
    for shot in shots:  # First, so a shot that can't be built changes nothing.
        if shot.name not in scenes:
            scenes[shot.name] = make_scene(shot)
            sync.added.append(shot.name)

    editor = master.sequence_editor
    assert editor is not None  # A master scene always has one (layout.start_cut).
    before = {}
    for strip in layout.shot_strips(master):
        shown = strip.scene
        assert shown is not None  # shot_strips only returns strips showing a shot.
        before[layout.strip_shot(strip)] = (strip.left_handle, shown.frame_start, shown.frame_end)
        editor.strips.remove(strip)
    for shot in shots:
        assert shot.frame_range is not None and shot.metadata.cut_in is not None  # in_cut.
        scene = scenes[shot.name]
        scene.frame_start, scene.frame_end = shot.frame_range
        layout.add_strip(master, scene, shot.metadata.cut_in)
        if shot.name in before and before[shot.name] != (shot.metadata.cut_in, *shot.frame_range):
            sync.retimed.append(shot.name)
    kept = {shot.name for shot in shots}
    sync.omitted = sorted(code for code in before if code not in kept)
    layout.fit_master_range(master)
    layout.sync_markers(master, sequence)
    return sync
