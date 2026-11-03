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
    """The master scene's active strip, if it's a shot's."""
    try:
        master = layout.master_scene()
    except PipelineError:
        return None
    active = master.sequence_editor.active_strip if master.sequence_editor else None
    return next((strip for strip in layout.shot_strips(master) if strip == active), None)


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
            cls.poll_message_set("Select a shot's strip in the cut.")
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
