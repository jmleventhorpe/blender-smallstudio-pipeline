"""The Shot panel: the shot on show, or the one selected in the cut.

In a shot's scene it shows that shot; in the cut (the master scene) it shows the shot
whose strip is selected. It gives the shot's frame range, where it sits in the cut, and
who's cast in it, with Go to Shot or Back to Cut, Add Shot and Omit Shot. It only shows in
a sequence's layout workfile.
"""

from __future__ import annotations

from typing import Any

import bpy

from ...common.errors import PipelineError
from ...interface.panels import DASH, both_sidebars, pair, wrapped
from ...loading.blender import instances
from ...session import state
from . import layout
from .operators import selected_shot_strip


def shot_on_show(scene: bpy.types.Scene | None) -> tuple[bpy.types.Scene, Any] | None:
    """The shot scene to show and its strip in the cut (or None if it has none)."""
    try:
        master = layout.master_scene()
    except PipelineError:
        return None
    strips = layout.shot_strips(master)
    if scene is not None and layout.SHOT in scene:
        return scene, next((strip for strip in strips if strip.scene == scene), None)
    strip = selected_shot_strip()
    return (strip.scene, strip) if strip is not None and strip.scene is not None else None


class ShotPanel:
    """The shot on show, or selected in the cut: frames, cut, cast."""

    bl_label = "Shot"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        file = state.current.context
        return file is not None and file.task == layout.LAYOUT and not file.is_publish

    def draw(self: Any, context: bpy.types.Context) -> None:
        box = self.layout
        found = shot_on_show(context.scene)
        if found is None:
            wrapped(box, "Select a shot's strip in the cut to see it here.", icon="INFO")
        else:
            scene, strip = found
            pair(box, "Shot", str(scene[layout.SHOT]))
            length = scene.frame_end - scene.frame_start + 1
            pair(box, "Frames", f"{scene.frame_start}{DASH}{scene.frame_end}  ({length})")
            if strip is not None:
                pair(box, "Cut", f"{strip.left_handle}{DASH}{strip.right_handle - 1}")
            else:
                pair(box, "Cut", "not in the cut (omitted)")
            cast = [entry.instance_id or entry.asset for entry in instances.casting(scene)]
            pair(box, "Cast", ", ".join(cast) if cast else "nobody yet")
            if context.scene == scene:
                box.operator("pipeline.back_to_cut", icon="SEQUENCE")
            else:
                box.operator("pipeline.go_to_shot", icon="SCENE_DATA")
        row = box.row(align=True)
        row.operator("pipeline.add_shot", icon="ADD")
        row.operator("pipeline.omit_shot", icon="REMOVE")


CLASSES = both_sidebars(ShotPanel, "shot")
