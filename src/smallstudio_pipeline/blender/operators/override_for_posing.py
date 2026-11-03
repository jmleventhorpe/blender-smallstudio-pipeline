"""Pipeline > Override for Posing: make a linked asset in a shot posable, where it stands.

Used in a sequence's or shot's workfile; see blender/shots/instances.py for how the
override keeps its placement.
"""

from __future__ import annotations

import bpy

from ...core.errors import PipelineError
from .. import state
from ..identity import linked_asset
from ..shots import instances
from .common import has_project


class PIPELINE_OT_override_for_posing(bpy.types.Operator):
    """Override the selected linked asset so it can be posed, keeping where it stands"""

    bl_idname = "pipeline.override_for_posing"
    bl_label = "Override for Posing"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not has_project(cls):
            return False
        file = state.current.context
        if file is None or file.entity_kind == "asset" or file.is_publish:
            cls.poll_message_set("Override for Posing works in a sequence's or shot's workfile.")
            return False
        if linked_asset(context.active_object) is None:
            cls.poll_message_set("Select a linked asset (the empty that places it).")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        empty = context.active_object
        assert empty is not None  # Checked by poll.
        try:
            override = instances.override_for_posing(empty, context.scene, context.view_layer)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{override.name} can be posed now.")
        return {"FINISHED"}
