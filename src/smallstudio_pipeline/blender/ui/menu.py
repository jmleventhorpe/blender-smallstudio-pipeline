"""The Pipeline menu, and the label in the top bar saying what the open file is.

Both read state.current and nothing else: the top bar redraws constantly, so nothing
here may touch the disk. Make Editable only appears when a linked asset is selected.
"""

from __future__ import annotations

import bpy

from .. import in_context, state


class PIPELINE_MT_main(bpy.types.Menu):
    bl_idname = "PIPELINE_MT_main"
    bl_label = "Pipeline"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        if state.current.warning:
            layout.label(text=state.current.warning, icon="ERROR")
            layout.separator()
        layout.operator("pipeline.open", text="Open…", icon="FILEBROWSER")
        layout.operator("pipeline.new_workfile", text="New Workfile…", icon="FILE_NEW")
        layout.operator("pipeline.new_asset", text="New Asset…", icon="ADD")
        layout.separator()
        layout.operator("pipeline.version_up", icon="DUPLICATE")
        layout.operator("pipeline.publish", icon="EXPORT")
        layout.operator("pipeline.check_updates", icon="FILE_REFRESH")
        # Below here, only what applies to the open file and selection.
        if in_context.linked_asset(context.active_object) is not None:
            layout.separator()
            layout.operator("pipeline.make_editable", icon="LIBRARY_DATA_OVERRIDE")


def draw_in_top_bar(self: bpy.types.Menu, context: bpy.types.Context) -> None:
    """Added after the top bar's menus: the Pipeline menu, then the open file's label."""
    self.layout.menu(PIPELINE_MT_main.bl_idname)
    row = self.layout.row()
    row.alert = state.current.warning is not None  # Draws in the warning colour.
    row.label(text=state.current.label, icon="ERROR" if state.current.warning else "NONE")


# The stubs say draw functions take (context); Blender calls them with (self, context).
def register() -> None:
    bpy.types.TOPBAR_MT_editor_menus.append(draw_in_top_bar)  # pyright: ignore[reportArgumentType]


def unregister() -> None:
    bpy.types.TOPBAR_MT_editor_menus.remove(draw_in_top_bar)  # pyright: ignore[reportArgumentType]


CLASSES = (PIPELINE_MT_main,)
