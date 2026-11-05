"""Add-on preferences: the project folders on this machine, and which one is active.

The active project is used when the open file isn't inside a project (a new, unsaved
file, say). The list lives in this machine's settings file (project/core/machine.py), not in
Blender's preferences, so it survives add-on updates and Blender upgrades: the page is
filled from the file when the add-on starts, and every change is written back to it.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import CollectionProperty, IntProperty, StringProperty

from ..core.machine import MachineSettings, ProjectFolder, load_settings, save_settings
from ..core.machine import settings_path as machine_settings_path

# The add-on's own module name: "smallstudio_pipeline", or "bl_ext.<repo>.smallstudio_pipeline"
# when installed as an extension. This module is <add-on>.project.blender.preferences.
ADDON_ID = __name__.removesuffix(".project.blender.preferences")

_loading = False  # True while the page is filled from the file, so it isn't written back.


def _changed(_self: object, context: bpy.types.Context | None) -> None:
    if not _loading:
        save_from_preferences()


class PIPELINE_PG_project_root(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", update=_changed)
    path: StringProperty(name="Folder", subtype="DIR_PATH", update=_changed)


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
        layout.label(text=f"Saved in {machine_settings_path()}", icon="FILE")


class PIPELINE_OT_add_project(bpy.types.Operator):
    bl_idname = "pipeline.add_project"
    bl_label = "Add Project"
    bl_options = {"INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        preferences = get_preferences(context)
        if preferences is None:
            return {"CANCELLED"}
        preferences.projects.add()
        save_from_preferences()
        return {"FINISHED"}


class PIPELINE_OT_remove_project(bpy.types.Operator):
    bl_idname = "pipeline.remove_project"
    bl_label = "Remove Project"
    bl_options = {"INTERNAL"}

    index: IntProperty()

    def execute(self, context: bpy.types.Context) -> set[str]:
        preferences = get_preferences(context)
        if preferences is None:
            return {"CANCELLED"}
        preferences.projects.remove(self.index)
        preferences.active_project = min(preferences.active_project, len(preferences.projects) - 1)
        save_from_preferences()
        return {"FINISHED"}


class PIPELINE_OT_use_project(bpy.types.Operator):
    bl_idname = "pipeline.use_project"
    bl_label = "Use Project"
    bl_description = "Use this project when the open file isn't in one"
    bl_options = {"INTERNAL"}

    index: IntProperty()

    def execute(self, context: bpy.types.Context) -> set[str]:
        preferences = get_preferences(context)
        if preferences is None:
            return {"CANCELLED"}
        preferences.active_project = self.index
        save_from_preferences()
        return {"FINISHED"}


def get_preferences(context: bpy.types.Context | None = None) -> PIPELINE_AP_preferences | None:
    """The add-on's preferences, or None when it's registered without being enabled (tests)."""
    addon = (context or bpy.context).preferences.addons.get(ADDON_ID)
    return addon.preferences if addon else None  # type: ignore[return-value]


def load_into_preferences() -> None:
    """Fill the preferences page from this machine's settings file."""
    global _loading
    preferences = get_preferences()
    if preferences is None:
        return
    settings = load_settings()
    _loading = True
    try:
        preferences.projects.clear()
        for folder in settings.projects:
            entry = preferences.projects.add()
            entry.name, entry.path = folder.name, folder.path
        preferences.active_project = settings.active
    finally:
        _loading = False


def save_from_preferences() -> None:
    """Write the preferences page to this machine's settings file, then use what changed."""
    preferences = get_preferences()
    if preferences is None:
        return
    folders = [
        ProjectFolder(p.name, bpy.path.abspath(p.path) if p.path else "")
        for p in preferences.projects
    ]
    save_settings(MachineSettings(folders, preferences.active_project))
    from ...session import handlers, state

    state.refresh()
    handlers.after_open()


def active_project_root() -> Path | None:
    """The active project's folder from this machine's settings, or None if there isn't one."""
    return load_settings().active_root


CLASSES = (
    PIPELINE_PG_project_root,
    PIPELINE_AP_preferences,
    PIPELINE_OT_add_project,
    PIPELINE_OT_remove_project,
    PIPELINE_OT_use_project,
)
