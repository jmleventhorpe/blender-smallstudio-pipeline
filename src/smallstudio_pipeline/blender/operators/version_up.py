from __future__ import annotations

from pathlib import Path

import bpy

from ...core.errors import PipelineError
from ...core.workfiles import version_up_path
from .. import state
from .common import has_project


class PIPELINE_OT_version_up(bpy.types.Operator):
    """Save the open workfile as the task's next version"""

    bl_idname = "pipeline.version_up"
    bl_label = "Version Up"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not has_project(cls):
            return False
        if state.current.context is None or state.current.context.is_publish:
            cls.poll_message_set("Open a pipeline workfile to version it up.")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        assert project is not None  # Checked by poll.
        try:
            path = version_up_path(project, Path(bpy.data.filepath))
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        state.refresh()
        self.report({"INFO"}, f"Saved {path.name}")
        return {"FINISHED"}
