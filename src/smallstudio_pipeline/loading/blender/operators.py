"""Loading's menu actions: Check Updates, Make Editable and Override for Posing.

Pipeline > Check Updates: reload linked publishes that were published again, and say
which, along with anything built from an older publish.

Pipeline > Make Editable: swap the selected linked asset for a local copy to edit here.

Publishing the copy links the asset back in; see loading/blender/editable.py.

Pipeline > Override for Posing: make a linked asset in a shot posable, where it stands.

Used in a sequence's or shot's workfile; see loading/blender/instances.py for how the
override keeps its placement.
"""

from __future__ import annotations

from typing import Any

import bpy
from bpy.props import StringProperty

from ...common.errors import PipelineError
from ...interface.common import has_project
from ...project.blender.identity import linked_asset
from ...session import state
from . import editable, instances, updates


class PIPELINE_OT_check_updates(bpy.types.Operator):
    """Reload linked publishes that have been published again since this file opened"""

    bl_idname = "pipeline.check_updates"
    bl_label = "Check Updates"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        assert project is not None  # Checked by poll.
        changes = updates.reload_changed(project)
        stale = updates.stale_builds(project, context.scene)
        news = []
        if changes:
            news.append("Updated " + ", ".join(change.label for change in changes))
        if stale:
            news.append(updates.stale_warning(stale))
        self.report(
            {"WARNING" if stale else "INFO"}, ". ".join(news) or "Everything is up to date."
        )
        return {"FINISHED"}


class PIPELINE_OT_make_editable(bpy.types.Operator):
    """Swap the selected linked asset for a local copy to edit here. Publish it to link it again"""

    bl_idname = "pipeline.make_editable"
    bl_label = "Make Editable"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not has_project(cls):
            return False
        file = state.current.context
        if file is None or file.entity_kind != "asset" or file.is_publish:
            cls.poll_message_set("Make Editable works in an asset's workfile, such as a set's.")
            return False
        if linked_asset(context.active_object) is None:
            cls.poll_message_set("Select a linked asset (the empty that places it).")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        assert project is not None and context.active_object is not None  # Checked by poll.
        try:
            root = editable.make_editable(context.active_object, project, context.view_layer)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{root.name} is editable here. Publish it to link it again.")
        return {"FINISHED"}


def in_shot_workfile(operator_class: Any) -> bool:
    """Poll check: only in a sequence's or shot's workfile."""
    if not has_project(operator_class):
        return False
    file = state.current.context
    if file is None or file.entity_kind == "asset" or file.is_publish:
        operator_class.poll_message_set("This works in a sequence's or shot's workfile.")
        return False
    return True


def chosen_instance(operator: Any, context: bpy.types.Context) -> instances.Instance | None:
    """The instance a panel row named (holder), or else the one holding the selection."""
    if operator.holder:
        for instance in instances.instances(context.scene):
            if instance.holder.name == operator.holder:
                return instance
        return None
    return instances.instance_of(context.active_object, context.scene)


class PIPELINE_OT_override_for_posing(bpy.types.Operator):
    """Override the linked asset so it can be posed, keeping where it stands"""

    bl_idname = "pipeline.override_for_posing"
    bl_label = "Override for Posing"
    bl_options = {"REGISTER", "UNDO"}

    holder: StringProperty(options={"HIDDEN", "SKIP_SAVE"})  # Set by the Loaded panel.

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return in_shot_workfile(cls)

    def execute(self, context: bpy.types.Context) -> set[str]:
        instance = chosen_instance(self, context)
        if instance is None or instance.overridden:
            self.report({"ERROR"}, "Select a linked asset (the empty that places it).")
            return {"CANCELLED"}
        assert isinstance(instance.holder, bpy.types.Object)  # Not overridden: an empty.
        try:
            override = instances.override_for_posing(
                instance.holder, context.scene, context.view_layer
            )
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{override.name} can be posed now.")
        return {"FINISHED"}


class PIPELINE_OT_back_to_link(bpy.types.Operator):
    """Undo Override for Posing: link the asset again where it stands. Its pose is lost"""

    bl_idname = "pipeline.back_to_link"
    bl_label = "Back to Link"
    bl_options = {"REGISTER", "UNDO"}

    holder: StringProperty(options={"HIDDEN", "SKIP_SAVE"})  # Set by the Loaded panel.

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return in_shot_workfile(cls)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return context.window_manager.invoke_confirm(
            self,
            event,
            message="Link it again? Its pose here is lost.",
            confirm_text="Back to Link",
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        instance = chosen_instance(self, context)
        if instance is None or not instance.overridden:
            self.report({"ERROR"}, "Select an asset overridden for posing.")
            return {"CANCELLED"}
        assert isinstance(instance.holder, bpy.types.Collection)  # Overridden: a collection.
        try:
            empty = instances.back_to_link(instance.holder)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{empty.name} is linked again.")
        return {"FINISHED"}


class PIPELINE_OT_select_instance(bpy.types.Operator):
    """Select this instance: its empty, or its override's objects"""

    bl_idname = "pipeline.select_instance"
    bl_label = "Select"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    holder: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        instance = chosen_instance(self, context)
        if instance is None:
            return {"CANCELLED"}
        holder = instance.holder
        if isinstance(holder, bpy.types.Object):
            chosen = [holder]
        else:
            chosen = [*holder.all_objects, *filter(None, [instances.placing_empty(holder)])]
        for obj in context.view_layer.objects:
            obj.select_set(obj in chosen)
        if chosen:
            context.view_layer.objects.active = chosen[0]
        return {"FINISHED"}


class PIPELINE_OT_update_publish(bpy.types.Operator):
    """Reload this publish, so it shows its latest version"""

    bl_idname = "pipeline.update_publish"
    bl_label = "Update"
    bl_options = {"REGISTER", "INTERNAL"}

    path: StringProperty(options={"HIDDEN", "SKIP_SAVE"})  # Relative to the project.

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        if project is None:
            return {"CANCELLED"}
        updates.reload_one(project, self.path)
        return {"FINISHED"}


class PIPELINE_OT_refresh_versions(bpy.types.Operator):
    """Look again for newer publishes of what this file links"""

    bl_idname = "pipeline.refresh_versions"
    bl_label = "Refresh"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        if project is None:
            return {"CANCELLED"}
        updates.refresh_latest(project)
        return {"FINISHED"}


CLASSES = (
    PIPELINE_OT_check_updates,
    PIPELINE_OT_make_editable,
    PIPELINE_OT_override_for_posing,
    PIPELINE_OT_back_to_link,
    PIPELINE_OT_select_instance,
    PIPELINE_OT_update_publish,
    PIPELINE_OT_refresh_versions,
)
