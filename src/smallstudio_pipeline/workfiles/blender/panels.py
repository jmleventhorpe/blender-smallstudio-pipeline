"""The Workfiles panel: browse the project's workfiles without opening a dialog first.

Choose a type, an entity and a task to see its workfiles, newest first, with when each
was saved, and open one (through the Open dialog, which asks about unsaved changes) or
start the task's first. The choices live on the window manager (Browse); the list is
read when they change or on Refresh, so drawing never reads the disk.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty

from ...common.errors import PipelineError
from ...interface import browse
from ...interface.panels import both_sidebars, wrapped
from ...session import state

# The chosen task's workfiles, newest first: (version, file name, when it was saved).
listing: list[tuple[int, str, str]] = []


def refresh(choices: Any) -> None:
    """Read the chosen task's workfiles again."""
    listing.clear()
    try:
        entity = browse.selected_entity(choices)
        if entity is None or choices.task == browse.NONE:
            return
        for version in reversed(entity.workfile_versions(choices.task)):
            path = entity.workfile_path(choices.task, version)
            saved = datetime.fromtimestamp(path.stat().st_mtime).strftime("%d %b %H:%M")
            listing.append((version, path.name, saved))
    except (PipelineError, OSError):
        listing.clear()


def _category_changed(choices: Any, context: bpy.types.Context | None) -> None:
    browse.reset_entity(choices, context)


def _entity_changed(choices: Any, context: bpy.types.Context | None) -> None:
    browse.reset_task(choices, context)


def _task_changed(choices: Any, context: bpy.types.Context | None) -> None:
    refresh(choices)


class PIPELINE_PG_browse(bpy.types.PropertyGroup):
    # The browse callbacks read these, as they do the Open dialog's.
    existing_only: BoolProperty(default=False, options={"HIDDEN"})
    category: EnumProperty(name="Type", items=browse.category_items, update=_category_changed)
    entity: EnumProperty(name="Name", items=browse.entity_items, update=_entity_changed)
    task: EnumProperty(name="Task", items=browse.task_items, update=_task_changed)


class PIPELINE_OT_refresh_workfiles(bpy.types.Operator):
    """Look again for the chosen task's workfiles"""

    bl_idname = "pipeline.refresh_workfiles"
    bl_label = "Refresh"
    bl_options = {"INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        refresh(context.window_manager.pipeline_browse)  # pyright: ignore[reportAttributeAccessIssue]
        return {"FINISHED"}


class WorkfilesPanel:
    """Browse the project's workfiles: a task's versions, newest first."""

    bl_label = "Workfiles"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return state.current.project is not None

    def draw(self: Any, context: bpy.types.Context) -> None:
        layout = self.layout
        choices = context.window_manager.pipeline_browse  # pyright: ignore[reportAttributeAccessIssue]
        column = layout.column(align=True)
        for name in ("category", "entity", "task"):
            column.prop(choices, name)
        if browse.NONE in (choices.category, choices.entity, choices.task):
            wrapped(layout, "Nothing to browse here yet.", icon="INFO")
            return
        if not listing:
            wrapped(layout, "No workfiles yet for this task.", icon="INFO")
            start = layout.operator("pipeline.new_workfile", text="Start It", icon="FILE_NEW")
            start.category, start.entity, start.task = (
                choices.category,
                choices.entity,
                choices.task,
            )
        for version, name, saved in listing:
            row = layout.row(align=True)
            row.label(text=name, icon="FILE_BLEND")
            row.label(text=saved)
            opener = row.operator("pipeline.open", text="", icon="FILEBROWSER")
            opener.category, opener.entity = choices.category, choices.entity
            opener.task, opener.version = choices.task, str(version)
        layout.operator("pipeline.refresh_workfiles", icon="FILE_REFRESH")


def register() -> None:
    """Keep the panel's choices on the window manager."""
    bpy.types.WindowManager.pipeline_browse = PointerProperty(type=PIPELINE_PG_browse)  # pyright: ignore[reportAttributeAccessIssue]


def unregister() -> None:
    del bpy.types.WindowManager.pipeline_browse  # pyright: ignore[reportAttributeAccessIssue]


CLASSES = (
    PIPELINE_PG_browse,
    PIPELINE_OT_refresh_workfiles,
    *both_sidebars(WorkfilesPanel, "workfiles"),
)
