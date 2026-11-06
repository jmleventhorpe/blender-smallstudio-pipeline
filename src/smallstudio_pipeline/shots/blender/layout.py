"""The sequence layout file: a master scene holding the cut, and a scene per shot.

The master scene is named after the sequence and has a scene strip per shot, each
showing that shot's scene (the Storypencil pattern). start_cut() turns a new layout
workfile's scene into the master. add_shot() creates a shot after the strip at the
playhead: its code goes between its neighbours' (0015 between 0010 and 0020), its scene
gets a camera and starts at the project's shot_start, and later strips move along to
make room. show_cut_in_sequencer() points each workspace's Video Sequencer at the cut.
omit_shot() takes a shot's strip out of the cut and marks the shot omitted;
its scene stays in the file. sync_ranges() makes each shot scene's range what its strip
shows, so retiming in the cut is what layout publishes. set_playblast_output() points the
master scene's output at the sequence's layout render folder for the workfile's version.

Each shot scene has a root collection named after the shot, carrying its code like the
scene does: the shot's camera and placed assets go in it, and it's what you select to see
the shot. ensure_shot_root() gives scenes from before shot roots one. sync_markers() keeps
a timeline marker per shot ("0015"), at its strip in the cut and at the start of its scene.
"""

from __future__ import annotations

import math
from typing import cast

import bpy

from ...common.errors import PipelineError
from ...project.core.entities import Sequence, Shot
from ...project.core.metadata import CastEntry
from ..core.layout import ShotCut

LAYOUT = "layout"  # The task whose workfiles hold the cut.
SEQUENCE = "pipeline_sequence"  # On the master scene: the sequence's code.
SHOT = "pipeline_shot"  # On each shot scene: the shot's code.
NEW_SHOT_LENGTH = 48  # Frames: two seconds at 24 fps.
CHANNEL = 1


def start_cut(scene: bpy.types.Scene, sequence: Sequence) -> None:
    """Make a new layout workfile's scene the sequence's master scene."""
    scene.name = sequence.name
    scene[SEQUENCE] = sequence.name
    scene.sequence_editor_create()
    scene.frame_start = scene.frame_end = 1
    show_cut_in_sequencer(scene)


def show_cut_in_sequencer(master: bpy.types.Scene) -> None:
    """Make each workspace's Video Sequencer edit the cut, where it edits no scene yet.

    Blender 5 gives every workspace a sequencer scene of its own, apart from the scene on
    show; a new file has none, so a sequencer opened there would have nothing to edit.
    """
    for workspace in bpy.data.workspaces:
        if workspace.sequencer_scene is None:
            workspace.sequencer_scene = master


def master_scene() -> bpy.types.Scene:
    """The open layout file's master scene."""
    for scene in bpy.data.scenes:
        if SEQUENCE in scene:
            return scene
    raise PipelineError("This file has no master scene, so it isn't a sequence layout file.")


def shot_strips(master: bpy.types.Scene) -> list[bpy.types.SceneStrip]:
    """The master scene's shot strips, in cut order."""
    strips = [
        strip
        for strip in master.sequence_editor.strips
        if isinstance(strip, bpy.types.SceneStrip) and strip.scene and SHOT in strip.scene
    ]
    return sorted(strips, key=lambda strip: strip.left_handle)


def strip_shot(strip: bpy.types.SceneStrip) -> str:
    """The code of the shot a strip shows."""
    assert strip.scene is not None  # shot_strips only returns strips showing a shot.
    return str(strip.scene[SHOT])


def add_shot(sequence: Sequence, master: bpy.types.Scene, frame: int) -> Shot:
    """Add a shot after the strip at (or before) frame, moving later strips along."""
    strips = shot_strips(master)
    before = [strip for strip in strips if strip.left_handle <= frame]
    if before:
        shot = sequence.create_shot(after=sequence.project.shot(strip_shot(before[-1])))
        start = before[-1].right_handle
    else:
        shot = sequence.create_shot(first=bool(strips))
        start = master.frame_start
    for strip in reversed(strips[len(before) :]):  # Last first, so strips never overlap.
        strip.content_start += NEW_SHOT_LENGTH

    scene = new_shot_scene(shot, master)
    new = master.sequence_editor.strips.new_scene(shot.name, scene, CHANNEL, start)
    strip = cast(bpy.types.SceneStrip, new)
    strip.scene_camera = scene.camera
    for other in master.sequence_editor.strips:  # Select the new shot, as clicking it would.
        other.select = False
    strip.select = True
    master.sequence_editor.active_strip = strip
    fit_master_range(master)
    sync_markers(master, sequence)
    return shot


def new_shot_scene(shot: Shot, master: bpy.types.Scene) -> bpy.types.Scene:
    """A scene for the shot, with a camera, taking the master's frame rate and resolution."""
    scene = bpy.data.scenes.new(shot.name)
    scene[SHOT] = shot.name
    scene.frame_start = shot.project.config.shot_start
    scene.frame_end = scene.frame_start + NEW_SHOT_LENGTH - 1
    scene.render.fps, scene.render.fps_base = master.render.fps, master.render.fps_base
    scene.render.resolution_x = master.render.resolution_x
    scene.render.resolution_y = master.render.resolution_y
    scene.render.resolution_percentage = master.render.resolution_percentage

    root = ensure_shot_root(scene)
    camera = bpy.data.objects.new(f"{shot.name}_cam", bpy.data.cameras.new(f"{shot.name}_cam"))
    camera.location = (0.0, -12.0, 2.0)
    camera.rotation_euler = (math.radians(85), 0.0, 0.0)
    root.objects.link(camera)
    scene.camera = camera
    return scene


def shot_root(scene: bpy.types.Scene) -> bpy.types.Collection | None:
    """A shot scene's root collection, if it has one."""
    code = scene.get(SHOT)
    for collection in scene.collection.children:
        if code is not None and collection.get(SHOT) == code:
            return collection
    return None


def ensure_shot_root(scene: bpy.types.Scene) -> bpy.types.Collection:
    """The shot scene's root collection, made if it hasn't one, as the active collection.

    A new root takes the scene's loose objects. Being active, it's where assets dragged in
    from the Asset Browser land.
    """
    root = shot_root(scene)
    if root is None:
        root = bpy.data.collections.new(str(scene[SHOT]))
        root[SHOT] = scene[SHOT]
        scene.collection.children.link(root)
        for obj in list(scene.collection.objects):
            root.objects.link(obj)
            scene.collection.objects.unlink(obj)
    for view_layer in scene.view_layers:
        if view_layer.layer_collection is None:  # A new scene's, until Blender updates it.
            view_layer.update()
        if view_layer.layer_collection is None:
            continue
        found = view_layer.layer_collection.children.get(root.name)
        if found is not None:
            view_layer.active_layer_collection = found
    return root


def shot_number(code: str) -> str:
    """The shot's own number, e.g. "0015" for "010_010_0015": what markers show."""
    return code.rpartition("_")[2]


def sync_markers(master: bpy.types.Scene, sequence: Sequence) -> None:
    """A marker per shot in the cut at its strip, and one at the start of each shot scene.

    Markers named after one of the sequence's shots are the pipeline's: they're moved,
    added and removed to match. Other markers are left alone.
    """
    numbers = {shot_number(shot.name) for shot in sequence.shots(include_omitted=True)}
    strips = shot_strips(master)
    numbers |= {shot_number(strip_shot(strip)) for strip in strips}
    wanted = {shot_number(strip_shot(strip)): strip.left_handle for strip in strips}
    _set_markers(master, numbers, wanted)
    for strip in strips:
        scene = strip.scene
        assert scene is not None  # shot_strips only returns strips showing a shot.
        _set_markers(scene, numbers, {shot_number(strip_shot(strip)): scene.frame_start})


def _set_markers(scene: bpy.types.Scene, ours: set[str], wanted: dict[str, int]) -> None:
    markers = scene.timeline_markers
    for marker in [m for m in markers if m.name in ours and m.name not in wanted]:
        markers.remove(marker)
    for name, frame in wanted.items():
        marker = markers.get(name) or markers.new(name, frame=frame)
        marker.frame = frame


def omit_shot(strip: bpy.types.SceneStrip, sequence: Sequence, master: bpy.types.Scene) -> Shot:
    """Take a shot's strip out of the cut, close the gap, and mark the shot omitted."""
    shot = sequence.project.shot(strip_shot(strip))
    length = strip.duration
    later = [s for s in shot_strips(master) if s.left_handle > strip.left_handle]
    master.sequence_editor.strips.remove(strip)
    for other in later:  # First first, so strips never overlap.
        other.content_start -= length
    fit_master_range(master)
    shot.omit()
    sync_markers(master, sequence)
    return shot


def fit_master_range(master: bpy.types.Scene) -> None:
    """Make the master scene's range cover the cut."""
    strips = shot_strips(master)
    master.frame_end = strips[-1].right_handle - 1 if strips else master.frame_start


def sync_ranges(master: bpy.types.Scene) -> None:
    """Make each shot scene's range the frames its strip shows, keeping the cut as it is.

    Trimming a strip only hides frames of its scene, so the trim moves into the scene's
    range and the strip shows all of it again. A strip keeps the length it was made with
    when its scene's range changes, so its length is set again too.
    """
    for strip in shot_strips(master):
        scene = strip.scene
        first = scene.frame_start + int(strip.left_handle_offset)
        cut_in, length = strip.left_handle, strip.duration
        scene.frame_start, scene.frame_end = first, first + length - 1
        strip.left_handle_offset = strip.right_handle_offset = 0
        strip.content_start = cut_in
        strip.duration = length


def set_playblast_output(master: bpy.types.Scene, sequence: Sequence, version: int) -> None:
    """Point the master scene's output at this version's layout render folder."""
    folder = sequence.render_path(LAYOUT, version)
    master.render.filepath = str(folder / f"{sequence.name}_{LAYOUT}_")


def cut(master: bpy.types.Scene, casting: dict[str, tuple[CastEntry, ...]]) -> list[ShotCut]:
    """The cut as ShotCuts, in order, with each shot's casting from `casting` by code."""
    cuts = []
    for strip in shot_strips(master):
        scene, code = strip.scene, strip_shot(strip)
        first = scene.frame_start + int(strip.left_handle_offset)
        length = strip.duration
        cut_in = strip.left_handle
        last, cut_out = first + length - 1, cut_in + length - 1
        cuts.append(ShotCut(code, first, last, cut_in, cut_out, casting.get(code, ())))
    return cuts
