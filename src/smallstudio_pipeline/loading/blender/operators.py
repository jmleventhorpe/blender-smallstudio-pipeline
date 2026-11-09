"""Loading's menu actions: Check Updates, Make Editable, Override and Back to Link.

Pipeline > Check Updates: reload linked publishes that were published again, and say
which.

Pipeline > Make Editable: swap the selected linked asset for a local copy to edit here,
in any file. Publishing the copy (with Link Back) links the asset in again; see
loading/blender/editable.py.

Pipeline > Override: override the selected linked asset where it stands, in any file, to
pose it or, for a set, move its pieces in this shot only. See loading/blender/instances.py
for how the override keeps its placement.

Pipeline > Back to Link: undo either, throwing away what was changed here.
"""

from __future__ import annotations

import bpy

from ...common.errors import PipelineError
from ...interface.common import has_project
from ...project.blender import nodes
from ...project.core.project import Project
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
        if changes:
            self.report({"INFO"}, "Updated " + ", ".join(change.label for change in changes))
        else:
            self.report({"INFO"}, "Everything is up to date.")
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
        if not instances.places_link(context.active_object):
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


class PIPELINE_OT_override(bpy.types.Operator):
    """Override the linked asset where it stands, to pose it or move a set's pieces here"""

    bl_idname = "pipeline.override"
    bl_label = "Override"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not has_project(cls):
            return False
        if not instances.places_link(context.active_object):
            cls.poll_message_set("Select a linked asset (the empty that places it).")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        assert context.active_object is not None  # Checked by poll.
        try:
            root = instances.override(context.active_object, context.scene, context.view_layer)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{root.name} is overridden: change it here.")
        return {"FINISHED"}


class PIPELINE_OT_back_to_link(bpy.types.Operator):
    """Link the asset again where it stands, throwing away what was changed here"""

    bl_idname = "pipeline.back_to_link"
    bl_label = "Back to Link"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not has_project(cls):
            return False
        if not can_go_back(context.active_object, context.scene):
            cls.poll_message_set("Select an overridden or made-editable asset.")
            return False
        return True

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return context.window_manager.invoke_confirm(
            self,
            event,
            message="Link it again? What was changed here is lost.",
            confirm_text="Back to Link",
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        assert project is not None  # Checked by poll.
        obj, scene = context.active_object, context.scene
        try:
            copy = editable.editable_copy(obj, scene)
            if copy is not None:
                empty = link_copy_again(copy, project, scene)
            else:
                instance = instances.instance_of(obj, scene)
                assert instance is not None and instance.overridden  # Checked by poll.
                assert isinstance(instance.holder, bpy.types.Collection)
                empty = instances.back_to_link(instance.holder)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{empty.name} is linked again.")
        return {"FINISHED"}


def can_go_back(obj: bpy.types.Object | None, scene: bpy.types.Scene) -> bool:
    """Whether an object is part of an override or a made-editable copy: Back to Link."""
    if editable.editable_copy(obj, scene) is not None:
        return True
    instance = instances.instance_of(obj, scene)
    return instance is not None and instance.overridden


def link_copy_again(
    copy: bpy.types.Collection, project: Project, scene: bpy.types.Scene
) -> bpy.types.Object:
    """Throw a made-editable copy away, linking its asset's hero where it stood."""
    node = nodes.node_of(copy)
    if node is None or node.kind != "asset":
        raise PipelineError(f"{copy.name} isn't an asset's copy, so it can't be linked again.")
    asset = project.asset(node.name)
    task = node.task or asset.tasks[0]
    hero = asset.hero_path(task)
    if not hero.exists():
        raise PipelineError(f"{asset.name} has no {task} publish to link.")
    return editable.link_again(copy, asset, hero, scene)


CLASSES = (
    PIPELINE_OT_check_updates,
    PIPELINE_OT_make_editable,
    PIPELINE_OT_override,
    PIPELINE_OT_back_to_link,
)
