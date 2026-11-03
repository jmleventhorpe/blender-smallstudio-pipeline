"""Add-on preferences: this machine's project roots. A fuller settings page comes later."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import CollectionProperty, IntProperty, StringProperty

# The add-on's own module name: "smallstudio_pipeline", or "bl_ext.<repo>.smallstudio_pipeline"
# when installed as an extension. This module is <add-on>.blender.ui.preferences.
ADDON_ID = __name__.removesuffix(".blender.ui.preferences")


class PIPELINE_PG_project_root(bpy.types.PropertyGroup):
    name: StringProperty(name="Name")
    path: StringProperty(name="Folder", subtype="DIR_PATH")


class PIPELINE_AP_preferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    projects: CollectionProperty(type=PIPELINE_PG_project_root)
    active_project: IntProperty(
        name="Active Project",
        description="The project used when the open file isn't in one",
        default=0,
    )

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="Project folders on this machine (the folder with pipeline.toml):")
        for index, project in enumerate(self.projects):
            row = layout.row(align=True)
            active = index == self.active_project
            use = row.operator(
                "pipeline.use_project", text="", icon="RADIOBUT_ON" if active else "RADIOBUT_OFF"
            )
            use.index = index
            row.prop(project, "name", text="")
            row.prop(project, "path", text="")
            row.operator("pipeline.remove_project", text="", icon="X").index = index
        layout.operator("pipeline.add_project", icon="ADD")


class PIPELINE_OT_add_project(bpy.types.Operator):
    bl_idname = "pipeline.add_project"
    bl_label = "Add Project"
    bl_options = {"INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        get_preferences(context).projects.add()
        return {"FINISHED"}


class PIPELINE_OT_remove_project(bpy.types.Operator):
    bl_idname = "pipeline.remove_project"
    bl_label = "Remove Project"
    bl_options = {"INTERNAL"}

    index: IntProperty()

    def execute(self, context: bpy.types.Context) -> set[str]:
        preferences = get_preferences(context)
        preferences.projects.remove(self.index)
        preferences.active_project = min(preferences.active_project, len(preferences.projects) - 1)
        return {"FINISHED"}


class PIPELINE_OT_use_project(bpy.types.Operator):
    bl_idname = "pipeline.use_project"
    bl_label = "Use Project"
    bl_description = "Use this project when the open file isn't in one"
    bl_options = {"INTERNAL"}

    index: IntProperty()

    def execute(self, context: bpy.types.Context) -> set[str]:
        get_preferences(context).active_project = self.index
        from .. import handlers, state  # Imported here: they import this module.

        state.refresh()
        handlers.after_open()
        return {"FINISHED"}


def get_preferences(context: bpy.types.Context | None = None) -> PIPELINE_AP_preferences:
    context = context or bpy.context
    return context.preferences.addons[ADDON_ID].preferences  # type: ignore[return-value]


def active_project_root() -> Path | None:
    """The active project's folder from the preferences, or None if there isn't one."""
    addon = bpy.context.preferences.addons.get(ADDON_ID)
    if addon is None:  # Registered without being enabled as an add-on, e.g. in tests.
        return None
    preferences = addon.preferences
    if not 0 <= preferences.active_project < len(preferences.projects):
        return None
    path = preferences.projects[preferences.active_project].path
    return Path(bpy.path.abspath(path)) if path else None


CLASSES = (
    PIPELINE_PG_project_root,
    PIPELINE_AP_preferences,
    PIPELINE_OT_add_project,
    PIPELINE_OT_remove_project,
    PIPELINE_OT_use_project,
)
