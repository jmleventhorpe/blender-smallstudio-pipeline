"""Pipeline > New Workfile: start a task's first workfile.

core/workfiles.py decides what it starts from; blender/workfiles.py starts it.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty

from ...core.errors import PipelineError
from ..ui import browse
from ..workfiles import start_workfile
from .common import UnsavedChanges, has_project


class PIPELINE_OT_new_workfile(UnsavedChanges, bpy.types.Operator):
    """Start a task's first workfile, from its starter file if it has one"""

    bl_idname = "pipeline.new_workfile"
    bl_label = "New Workfile"
    bl_options = {"REGISTER"}

    # A property, not a class attribute: the browse callbacks only see properties.
    # Offer every task; the core refuses ones already started.
    existing_only: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})

    kind: EnumProperty(name="Kind", items=browse.kind_items, update=browse.reset_entity)
    entity: EnumProperty(name="Name", items=browse.entity_items, update=browse.reset_task)
    task: EnumProperty(name="Task", items=browse.task_items)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        browse.preselect(self)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        for name in ("kind", "entity", "task"):
            self.layout.prop(self, name)
        self.draw_unsaved(self.layout)

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            entity = browse.selected_entity(self)
            if entity is None or self.task == browse.NONE:
                raise PipelineError("Choose what to start a workfile for.")
            self.handle_unsaved()
            task = self.task
            # Opening a file frees this operator, so nothing below may touch self.
            start_workfile(entity, task)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}
