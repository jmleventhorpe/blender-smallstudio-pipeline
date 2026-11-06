"""Workfiles' menu actions: Open, New Workfile, Save To and Version Up.

Pipeline > Open: open a workfile by type, name, task and version (newest first). The
choices come from interface/browse.py and start on the open file's own entity and task.
Unsaved changes are asked about first; the load handler then warns if someone else has
the file open.

Pipeline > New Workfile: start an empty file saved as a task's next workfile. Nothing is
added to it: New Node makes the nodes that say what it's working on.

Pipeline > Save To: save the open file as any asset's, sequence's or shot's task's next
workfile, so work started anywhere lands in the right place.

Pipeline > Version Up: save the open workfile as its task's next free version, which may
be beyond the current one + 1 if someone else saved since (workfiles/core/workfiles.py).
The save handler moves the in-use marker to the new file.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty

from ...common.errors import PipelineError
from ...interface import browse
from ...interface.common import UnsavedChanges, has_project
from ...project.core.entities import Entity
from ...session import state
from ..core.workfiles import version_up_path
from .workfiles import new_workfile, save_to


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
        if not self.properties.is_property_set("entity"):  # The Workfiles panel sets it.
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


class WorkfileChoice:
    """The type, name and task a workfile is for, as the browse callbacks need them."""

    # A property, not a class attribute: the browse callbacks only see properties.
    existing_only: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})

    category: EnumProperty(name="Type", items=browse.category_items, update=browse.reset_entity)
    entity: EnumProperty(name="Name", items=browse.entity_items, update=browse.reset_task)
    task: EnumProperty(name="Task", items=browse.task_items)

    def draw_choice(self, layout: bpy.types.UILayout | None) -> None:
        for name in ("category", "entity", "task"):
            layout.prop(self, name)

    def chosen(self) -> tuple[Entity, str]:
        entity = browse.selected_entity(self)
        if entity is None or self.task == browse.NONE:
            raise PipelineError("Choose an asset, sequence or shot and a task.")
        return entity, self.task


class PIPELINE_OT_new_workfile(WorkfileChoice, UnsavedChanges, bpy.types.Operator):
    """Start an empty file, saved as a task's next workfile"""

    bl_idname = "pipeline.new_workfile"
    bl_label = "New Workfile"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        if not self.properties.is_property_set("entity"):  # The Workfiles panel sets it.
            browse.preselect(self)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        self.draw_choice(self.layout)
        self.draw_unsaved(self.layout)

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            entity, task = self.chosen()
            self.handle_unsaved()
            # Opening a file frees this operator, so nothing below may touch self.
            new_workfile(entity, task)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


class PIPELINE_OT_save_to(WorkfileChoice, bpy.types.Operator):
    """Save this file as a task's next workfile: any asset's, sequence's or shot's"""

    bl_idname = "pipeline.save_to"
    bl_label = "Save To"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        if not self.properties.is_property_set("entity"):
            browse.preselect(self)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        self.draw_choice(self.layout)

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            entity, task = self.chosen()
            path = save_to(entity, task)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Saved {path.name}")
        return {"FINISHED"}


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
        bpy.ops.wm.save_as_mainfile(filepath=str(path))  # The save handler refreshes the state.
        self.report({"INFO"}, f"Saved {path.name}")
        return {"FINISHED"}


CLASSES = (
    PIPELINE_OT_open,
    PIPELINE_OT_new_workfile,
    PIPELINE_OT_save_to,
    PIPELINE_OT_version_up,
)
