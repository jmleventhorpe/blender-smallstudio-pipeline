"""Workfiles' menu actions: Open, New Workfile, New Asset and Version Up.

Pipeline > Open: open a workfile by type, name, task and version (newest first).

The choices come from interface/browse.py and start on the open file's own entity and task.
Unsaved changes are asked about first; the load handler then warns if someone else has
the file open.

Pipeline > New Workfile: start a task's first workfile.

workfiles/core/workfiles.py decides what it starts from; workfiles/blender/workfiles.py
starts it.

Pipeline > New Asset: create an asset and open its first workfile.

With "Build in This File", the asset starts in the open file instead (a prop inside its
set, say); publishing it from there saves its first workfile and links it back.

Pipeline > Version Up: save the open workfile as its task's next free version.

The next free version may be beyond the current one + 1 if someone else saved since
(workfiles/core/workfiles.py). The save handler moves the in-use marker to the new file.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from ...common.errors import PipelineError
from ...interface import browse
from ...interface.browse import Items, category_items
from ...interface.common import UnsavedChanges, has_project
from ...project.blender.identity import create_root_collection
from ...session import state
from ..core.workfiles import version_up_path
from .workfiles import start_workfile


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


class PIPELINE_OT_new_workfile(UnsavedChanges, bpy.types.Operator):
    """Start a task's first workfile, from its starter file if it has one"""

    bl_idname = "pipeline.new_workfile"
    bl_label = "New Workfile"
    bl_options = {"REGISTER"}

    # A property, not a class attribute: the browse callbacks only see properties.
    # Offer every task; the core refuses ones already started.
    existing_only: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})

    category: EnumProperty(name="Type", items=browse.category_items, update=browse.reset_entity)
    entity: EnumProperty(name="Name", items=browse.entity_items, update=browse.reset_task)
    task: EnumProperty(name="Task", items=browse.task_items)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        if not self.properties.is_property_set("entity"):  # The Workfiles panel sets it.
            browse.preselect(self)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        for name in ("category", "entity", "task"):
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


def asset_type_items(operator: object, context: bpy.types.Context | None) -> Items:
    # The categories minus sequence and shot are exactly the asset types.
    """The project's asset types, for the Type menu."""
    items = category_items(operator, context)
    return [item for item in items if item[0] not in ("sequence", "shot")]


class PIPELINE_OT_new_asset(UnsavedChanges, bpy.types.Operator):
    """Create an asset and open its first workfile"""

    bl_idname = "pipeline.new_asset"
    bl_label = "New Asset"
    bl_options = {"REGISTER"}

    asset_type: EnumProperty(name="Type", items=asset_type_items)
    name: StringProperty(name="Name", description="Lowercase, e.g. street_lamp")
    here: BoolProperty(
        name="Build in This File",
        description="Start the asset here, e.g. a prop inside its set; publishing it links it back",
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        self.layout.prop(self, "asset_type")
        self.layout.prop(self, "name")
        if state.current.context is not None:  # Only inside a pipeline workfile.
            self.layout.prop(self, "here")
        if not self.here:
            self.draw_unsaved(self.layout)

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        assert project is not None  # Checked by poll.
        try:
            if self.here:
                asset = project.create_asset(self.asset_type, self.name)
                create_root_collection(asset, context.scene)
                self.report({"INFO"}, f"{asset.name} started here. Publish it to link it back.")
                return {"FINISHED"}
            self.handle_unsaved()
            asset = project.create_asset(self.asset_type, self.name)
            # Opening a file frees this operator, so nothing below may touch self.
            start_workfile(asset, asset.tasks[0])
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
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
    PIPELINE_OT_new_asset,
    PIPELINE_OT_version_up,
)
