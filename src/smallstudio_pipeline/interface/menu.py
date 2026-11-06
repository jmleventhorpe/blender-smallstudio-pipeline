"""The Pipeline menu, and the label in the top bar saying what the open file is.

Both read state.current and nothing else: the top bar redraws constantly, so nothing
here may touch the disk. Below the separator, only what applies: with a linked asset
selected, Make Editable in an asset's workfile and Override for Posing in a sequence's
or shot's; Add Shot and Omit Shot in a layout workfile.
"""

from __future__ import annotations

import bpy

from ..project.blender.identity import linked_asset
from ..session import state
from ..shots.blender.layout import LAYOUT, SEQUENCE, SHOT, shot_number


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
        if file.entity_kind == "asset" and selected_link:
            layout.separator()
            layout.operator("pipeline.make_editable", icon="LIBRARY_DATA_OVERRIDE")
        if file.entity_kind != "asset" and selected_link:
            layout.separator()
            layout.operator("pipeline.override_for_posing", icon="LIBRARY_DATA_OVERRIDE")
        if file.task == LAYOUT:
            layout.separator()
            layout.operator("pipeline.add_shot", icon="ADD")
            layout.operator("pipeline.omit_shot", icon="REMOVE")


def draw_in_top_bar(self: bpy.types.Menu, context: bpy.types.Context) -> None:
    """Added after the top bar's menus: the Pipeline menu, then the open file's label."""
    self.layout.menu(PIPELINE_MT_main.bl_idname)
    row = self.layout.row()
    row.alert = bool(state.current.warnings)  # Draws in the warning colour.
    text = state.current.label + scene_label(context.scene)
    row.label(text=text, icon="ERROR" if state.current.warnings else "NONE")


def scene_label(scene: bpy.types.Scene | None) -> str:
    """What the label adds for the scene on show: " · shot 0015", " · cut", or nothing."""
    if scene is not None and SHOT in scene:
        return f" · shot {shot_number(str(scene[SHOT]))}"
    if scene is not None and SEQUENCE in scene:
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
