"""The Publish panel: what Publish would write from the open file, and its checks.

Check fills it (publishing/blender/review.py): the asset or sequence it would publish,
the version it becomes, the facts that matter (the hero it replaces, materials, in
context), and for a layout a row per shot with its frames, cut, cast and what changed
since the last publish. Below, the last Check's or Publish's results, with Select and
Fix. It shows in any pipeline workfile.
"""

from __future__ import annotations

from typing import Any

import bpy

from ...interface.panels import both_sidebars, pair, wrapped
from ...session import state
from . import results, review


class PublishPanel:
    """What Publish would write from this file, and what the checks say."""

    bl_label = "Publish"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        file = state.current.context
        return state.current.project is not None and file is not None and not file.is_publish

    def draw(self: Any, context: bpy.types.Context) -> None:
        layout = self.layout
        row = layout.row(align=True)
        row.operator("pipeline.check_publish", icon="VIEWZOOM")
        row.operator("pipeline.publish", icon="EXPORT")
        preview = review.current
        if preview is None:
            if results.last is None or not results.last.published:
                wrapped(layout, "Check shows what Publish would write, and runs its checks.")
        else:
            box = layout.box()
            pair(box, "Publishes", preview.title)
            pair(box, "As", preview.writes)
            for fact in preview.facts:
                box.label(text=fact)
            if preview.shots:
                draw_shots(box, preview)
        results.draw_results(layout)


def draw_shots(layout: bpy.types.UILayout, preview: review.Preview) -> None:
    """A row per shot: number, frames, cut, cast, and what changed."""
    grid = layout.grid_flow(row_major=True, columns=5, even_columns=False, align=True)
    for heading in ("Shot", "Frames", "Cut", "Cast", "Change"):
        cell = grid.row()
        cell.enabled = False
        cell.label(text=heading)
    for shot in preview.shots:
        grid.label(text=shot.shot)
        grid.label(text=shot.frames)
        grid.label(text=shot.cut)
        grid.label(text=str(shot.cast))
        cell = grid.row()
        cell.alert = bool(shot.change)
        cell.label(text=shot.change or "-")
    for number in preview.omitted:
        row = layout.row()
        row.alert = True
        row.label(text=f"{number} will be omitted (no strip in the cut)", icon="REMOVE")


CLASSES = both_sidebars(PublishPanel, "publish")
