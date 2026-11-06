"""The Loaded panel: every asset instance in the scene on show, and how current it is.

Each row is an instance: its ID (or its empty's name before the shot is saved), the asset,
the task and version loaded, and whether a newer version has been published. Versions come
from loading/blender/updates.py's notes, made on opening and on Refresh, so drawing never
reads the disk. Row buttons select the instance, update it, and override it for posing
or link it back.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import bpy

from ...interface.panels import both_sidebars, wrapped
from ...publishing.core.publishing import relative
from ...session import state
from ...workfiles.core.context import file_context
from . import instances, updates


def version_text(number: int | None, padding: int) -> str:
    """e.g. "v003", or "v?" when the publish's record can't be read."""
    return "v?" if number is None else f"v{number:0{padding}d}"


class LoadedPanel:
    """Every instance in the scene, with its asset, version and whether it's current."""

    bl_label = "Loaded"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        scene = context.scene
        return (
            state.current.project is not None
            and scene is not None
            and bool(instances.instances(scene))
        )

    def draw(self: Any, context: bpy.types.Context) -> None:
        layout, project = self.layout, state.current.project
        assert project is not None  # Checked by poll.
        padding = project.config.version_padding
        file = state.current.context
        in_shot_file = file is not None and file.entity_kind != "asset" and not file.is_publish
        out_of_date = unknown = 0
        for instance in instances.instances(context.scene):
            library = instance.library
            path = relative(project, Path(bpy.path.abspath(library.filepath))) if library else ""
            loaded, newest = updates.seen.get(path), updates.latest.get(path)
            source = file_context(project, project.root / path) if path else None
            task = source.task if source else "?"
            stale = loaded is not None and newest is not None and newest > loaded
            unknown += path not in updates.seen

            row = layout.row(align=True)
            icon = "LIBRARY_DATA_OVERRIDE" if instance.overridden else "LINKED"
            row.label(text=instance.instance_id or instance.holder.name, icon=icon)
            row.label(text=f"{instance.asset} · {task} {version_text(loaded, padding)}")
            status = row.row(align=True)
            status.alert = stale
            if stale:
                out_of_date += 1
                status.label(text=f"{version_text(newest, padding)} out", icon="ERROR")
                status.operator("pipeline.update_publish", text="", icon="FILE_REFRESH").path = path
            else:
                status.label(text="", icon="CHECKMARK")
            select = row.operator("pipeline.select_instance", text="", icon="RESTRICT_SELECT_OFF")
            select.holder = instance.holder.name
            if in_shot_file and instance.overridden:
                back = row.operator("pipeline.back_to_link", text="", icon="LINKED")
                back.holder = instance.holder.name
            elif in_shot_file:
                pose = row.operator("pipeline.override_for_posing", text="", icon="ARMATURE_DATA")
                pose.holder = instance.holder.name
        if out_of_date:
            wrapped(layout, f"{out_of_date} out of date: Update All reloads them.", icon="INFO")
        if unknown:
            wrapped(layout, "Linked since the last look: Refresh (or save) to see versions.")
        row = layout.row(align=True)
        row.operator("pipeline.refresh_versions", icon="FILE_REFRESH")
        row.operator("pipeline.check_updates", text="Update All", icon="IMPORT")


CLASSES = both_sidebars(LoadedPanel, "loaded")
