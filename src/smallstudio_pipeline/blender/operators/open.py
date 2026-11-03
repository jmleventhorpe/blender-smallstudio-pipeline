"""Pipeline > Open: open a workfile by type, name, task and version (newest first).

The choices come from ui/browse.py and start on the open file's own entity and task.
Unsaved changes are asked about first; the load handler then warns if someone else has
the file open.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty

from ...core.errors import PipelineError
from ..ui import browse
from .common import UnsavedChanges, has_project


class PIPELINE_OT_open(UnsavedChanges, bpy.types.Operator):
    """Open a workfile: choose what it's for, the task and the version"""

    bl_idname = "pipeline.open"
    bl_label = "Open"
    bl_options = {"REGISTER"}

    # A property, not a class attribute: the browse callbacks only see properties.
    existing_only: BoolProperty(default=True, options={"HIDDEN", "SKIP_SAVE"})

    category: EnumProperty(name="Type", items=browse.category_items, update=browse.reset_entity)
    entity: EnumProperty(name="Name", items=browse.entity_items, update=browse.reset_task)
    task: EnumProperty(name="Task", items=browse.task_items, update=browse.reset_version)
    version: EnumProperty(name="Version", items=browse.version_items)  # Newest first.

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        browse.preselect(self)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        for name in ("category", "entity", "task", "version"):
            self.layout.prop(self, name)
        self.draw_unsaved(self.layout)

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            entity = browse.selected_entity(self)
            if entity is None or browse.NONE in (self.task, self.version):
                raise PipelineError("There's no workfile to open there.")
            path = entity.workfile_path(self.task, int(self.version))
            self.handle_unsaved()
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        # Opening a file frees this operator, so nothing after this may touch self.
        bpy.ops.wm.open_mainfile(filepath=str(path))
        return {"FINISHED"}
