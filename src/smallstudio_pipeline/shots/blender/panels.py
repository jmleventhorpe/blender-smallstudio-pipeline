"""The Shot panel: the shot you're in.

In a shot's scene it gives the shot's frame range, where it sits in the cut, and who's
cast in it, with Back to Cut. Follow the cut (Blender's Sync Scene Time) makes the scene on
show follow the playhead through the cut, so scrubbing the cut shows each shot in the 3D
viewport. Add Shot and Omit Shot sit below. It only shows in a sequence's layout workfile.
"""

from __future__ import annotations

from typing import Any

import bpy

from ...common.errors import PipelineError
from ...interface.panels import DASH, both_sidebars, pair, wrapped
from ...loading.blender import instances
from ...project.blender import nodes
from ...session import state
from . import layout


def shot_on_show(scene: bpy.types.Scene | None) -> tuple[bpy.types.Scene, Any] | None:
    """The shot scene on show and its strip in the cut (None if it has none), or None in
    the cut itself."""
    if scene is None or nodes.shot_node(scene) is None:
        return None
    try:
        strips = layout.shot_strips(layout.master_scene())
    except PipelineError:
        return scene, None
    return scene, next((strip for strip in strips if strip.scene == scene), None)


class ShotPanel:
    """The shot you're in: frames, cut, cast."""

    bl_label = "Shot"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return state.current.project is not None and layout.has_cut()

    def draw(self: Any, context: bpy.types.Context) -> None:
        box = self.layout
        workspace = getattr(context, "workspace", None)
        if workspace is not None:
            box.prop(workspace, "use_scene_time_sync", text="Follow the cut")
        found = shot_on_show(context.scene)
        if found is None:
            wrapped(
                box, "You're in the cut. Follow the cut and scrub to see each shot.", icon="INFO"
            )
        else:
            scene, strip = found
            shot = nodes.shot_node(scene)
            assert shot is not None  # shot_on_show only finds shot scenes.
            pair(box, "Shot", shot.name)
            length = scene.frame_end - scene.frame_start + 1
            pair(box, "Frames", f"{scene.frame_start}{DASH}{scene.frame_end}  ({length})")
            if strip is not None:
                pair(box, "Cut", f"{strip.left_handle}{DASH}{strip.right_handle - 1}")
            else:
                pair(box, "Cut", "not in the cut (omitted)")
            cast = [entry.instance_id or entry.asset for entry in instances.casting(scene)]
            pair(box, "Cast", ", ".join(cast) if cast else "nobody yet")
            box.operator("pipeline.back_to_cut", icon="SEQUENCE")
        row = box.row(align=True)
        row.operator("pipeline.add_shot", icon="ADD")
        row.operator("pipeline.omit_shot", icon="REMOVE")


CLASSES = both_sidebars(ShotPanel, "shot")
