"""Pipeline > New Asset: create an asset and open its first workfile.

With "Build in This File", the asset starts in the open file instead (a prop inside its
set, say); publishing it from there saves its first workfile and links it back.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from ...core.errors import PipelineError
from .. import state
from ..identity import create_root_collection
from ..ui.browse import Items, kind_items
from ..workfiles import start_workfile
from .common import UnsavedChanges, has_project


def asset_type_items(operator: object, context: bpy.types.Context | None) -> Items:
    # The browsing kinds minus sequence and shot are exactly the asset types.
    return [item for item in kind_items(operator, context) if item[0] not in ("sequence", "shot")]


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
