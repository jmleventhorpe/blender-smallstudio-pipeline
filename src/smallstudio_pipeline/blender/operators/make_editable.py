"""Pipeline > Make Editable: swap the selected linked asset for a local copy to edit here.

Publishing the copy links the asset back in; see blender/in_context.py.
"""

from __future__ import annotations

import bpy

from ...core.errors import PipelineError
from .. import in_context, state
from .common import has_project


class PIPELINE_OT_make_editable(bpy.types.Operator):
    """Swap the selected linked asset for a local copy to edit here. Publish it to link it again"""

    bl_idname = "pipeline.make_editable"
    bl_label = "Make Editable"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not has_project(cls):
            return False
        if in_context.linked_asset(context.active_object) is None:
            cls.poll_message_set("Select a linked asset (the empty that places it).")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        assert project is not None and context.active_object is not None  # Checked by poll.
        try:
            root = in_context.make_editable(context.active_object, project)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{root.name} is editable here. Publish it to link it again.")
        return {"FINISHED"}
