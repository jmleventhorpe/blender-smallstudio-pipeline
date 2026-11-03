"""Pipeline > Add Shot: add a shot to the cut, after the strip at the playhead.

The shot's folder and metadata are created straight away. Undoing removes its strip and
scene but not the shot; the next layout publish marks a shot with no strip omitted.
"""

from __future__ import annotations

import bpy

from ...core.errors import PipelineError
from .. import state
from ..shots import layout
from .common import has_project, in_layout_workfile


class PIPELINE_OT_add_shot(bpy.types.Operator):
    """Add a shot after the one at the playhead in the cut, with its own scene and camera"""

    bl_idname = "pipeline.add_shot"
    bl_label = "Add Shot"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls) and in_layout_workfile(cls)

    def execute(self, context: bpy.types.Context) -> set[str]:
        project, file = state.current.project, state.current.context
        assert project is not None and file is not None  # Checked by poll.
        try:
            master = layout.master_scene()
            shot = layout.add_shot(project.sequence(file.entity), master, master.frame_current)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Added shot {shot.name}")
        return {"FINISHED"}
