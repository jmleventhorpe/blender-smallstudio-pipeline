"""Pipeline > Omit Shot: take the selected shot's strip out of the cut.

The shot is marked omitted and keeps its number, folder and scene; nothing is deleted.
Adding a strip for its scene again brings it back at the next layout publish.
"""

from __future__ import annotations

import bpy

from ...core.errors import PipelineError
from .. import state
from ..shots import layout
from .common import has_project, in_layout_workfile


def selected_shot_strip() -> bpy.types.SceneStrip | None:
    """The shot strip selected in the cut: the active one, or else the only one selected."""
    try:
        master = layout.master_scene()
    except PipelineError:
        return None
    selected = [strip for strip in layout.shot_strips(master) if strip.select]
    active = master.sequence_editor.active_strip
    for strip in selected:
        if strip == active:
            return strip
    return selected[0] if len(selected) == 1 else None


class PIPELINE_OT_omit_shot(bpy.types.Operator):
    """Take the selected shot out of the cut. Its scene and files stay"""

    bl_idname = "pipeline.omit_shot"
    bl_label = "Omit Shot"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not (has_project(cls) and in_layout_workfile(cls)):
            return False
        if selected_shot_strip() is None:
            showing = getattr(context, "sequencer_scene", None)
            master = layout.master_scene()
            if showing is not None and showing != master:
                cls.poll_message_set(
                    f"The Video Sequencer is showing {showing.name}. Set it to {master.name}, "
                    "the cut, in the sequencer's header."
                )
            else:
                cls.poll_message_set("Select one shot's strip in the cut (in the Video Sequencer).")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        project, file, strip = state.current.project, state.current.context, selected_shot_strip()
        assert project is not None and file is not None and strip is not None  # Checked by poll.
        try:
            shot = layout.omit_shot(strip, project.sequence(file.entity), layout.master_scene())
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Omitted shot {shot.name}. Its scene stays in this file.")
        return {"FINISHED"}
