"""The Pipeline menu, and the label in the top bar saying what the open file is.

Both read state.current and nothing else: the top bar redraws constantly, so nothing
here may touch the disk. Below the separator, only what applies: with a linked asset
selected, Make Editable in an asset's workfile and Override for Posing in a sequence's
or shot's; Add Shot and Omit Shot in a layout workfile.
"""

from __future__ import annotations

import bpy

from ..loading.blender import instances
from ..project.blender import nodes
from ..project.blender.identity import linked_asset
from ..session import state
from ..shots.blender.layout import has_cut, shot_number


class PIPELINE_MT_main(bpy.types.Menu):
    bl_idname = "PIPELINE_MT_main"
    bl_label = "Pipeline"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        for warning in state.current.warnings:
            layout.label(text=warning, icon="ERROR")
        if state.current.warnings:
            layout.separator()
        layout.operator("pipeline.open", text="Open…", icon="FILEBROWSER")
        layout.operator("pipeline.new_workfile", text="New Workfile…", icon="FILE_NEW")
        layout.operator("pipeline.new_asset", text="New Asset…", icon="ADD")
        layout.operator("pipeline.new_sequence", text="New Sequence…", icon="SEQUENCE")
        layout.separator()
        layout.operator("pipeline.version_up", icon="DUPLICATE")
        layout.operator("pipeline.publish", icon="EXPORT")
        layout.operator("pipeline.check_updates", icon="FILE_REFRESH")
        # Below here, only what applies to the open file and selection.
        file = state.current.context
        if file is None or file.is_publish:
            return
        selected_link = linked_asset(context.active_object) is not None
        holder = nodes.node_holding(context.active_object, context.scene)
        if selected_link and holder is not None and holder.kind == "asset":
            layout.separator()
            layout.operator("pipeline.make_editable", icon="LIBRARY_DATA_OVERRIDE")
        if selected_link and holder is not None and holder.kind == "shot":
            layout.separator()
            layout.operator("pipeline.override_for_posing", icon="LIBRARY_DATA_OVERRIDE")
        elif posed_instance(context):
            layout.separator()
            layout.operator("pipeline.back_to_link", icon="LINKED")
        if has_cut():
            layout.separator()
            layout.operator("pipeline.add_shot", icon="ADD")
            layout.operator("pipeline.omit_shot", icon="REMOVE")


def posed_instance(context: bpy.types.Context) -> bool:
    """True when the selection belongs to an asset overridden for posing."""
    found = instances.instance_of(context.active_object, context.scene)
    return found is not None and found.overridden


def draw_in_top_bar(self: bpy.types.Menu, context: bpy.types.Context) -> None:
    """Added after the top bar's menus: the Pipeline menu, then the open file's label."""
    self.layout.menu(PIPELINE_MT_main.bl_idname)
    row = self.layout.row()
    row.alert = bool(state.current.warnings)  # Draws in the warning colour.
    text = state.current.label + scene_label(context.scene)
    row.label(text=text, icon="ERROR" if state.current.warnings else "NONE")


def scene_label(scene: bpy.types.Scene | None) -> str:
    """What the label adds for the scene on show: " · shot 0015", " · cut", or nothing."""
    shot = nodes.shot_node(scene)
    if shot is not None:
        return f" · shot {shot_number(shot.name)}"
    if nodes.sequence_node(scene) is not None:
        return " · cut"
    return ""


# The stubs say draw functions take (context); Blender calls them with (self, context).
def register() -> None:
    """Register the menu and add it, with the label, to the top bar."""
    bpy.utils.register_class(PIPELINE_MT_main)
    bpy.types.TOPBAR_MT_editor_menus.append(draw_in_top_bar)  # pyright: ignore[reportArgumentType]


def unregister() -> None:
    bpy.types.TOPBAR_MT_editor_menus.remove(draw_in_top_bar)  # pyright: ignore[reportArgumentType]
    bpy.utils.unregister_class(PIPELINE_MT_main)
