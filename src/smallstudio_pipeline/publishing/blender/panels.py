"""The Publish panel: the node Publish would work on, what it becomes, and its checks.

The node (project/blender/nodes.py) is shown straight away: its collection, what it
publishes and the version it becomes. Check adds the rest (publishing/blender/review.py):
the facts that matter (the hero it replaces, materials, made editable here), and for a
layout or animation a row per shot with its frames, cut and cast (and for layout, what
changed since the last publish), the chosen shot first. With no node picked, or a loaded
asset, it says why and greys out the buttons. Below, the last Check's or Publish's
results, with Select and Fix. It shows in any pipeline workfile.
"""

from __future__ import annotations

from typing import Any

import bpy

from ...common.errors import PipelineError
from ...interface.panels import both_sidebars, pair, wrapped
from ...project.blender.nodes import LoadedPicked, current_node
from ...session import state
from . import results, review


class PublishPanel:
    """The node Publish would work on, what it becomes, and what the checks say."""

    bl_label = "Publish"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        file = state.current.context
        return state.current.project is not None and file is not None and not file.is_publish

    def draw(self: Any, context: bpy.types.Context) -> None:
        layout, project, file = self.layout, state.current.project, state.current.context
        assert project is not None and file is not None  # Checked by poll.
        try:
            chosen = current_node(context)
            title, writes = review.describe(project, file, chosen)
        except PipelineError as error:
            wrapped(
                layout, str(error), icon="LINKED" if isinstance(error, LoadedPicked) else "INFO"
            )
            row = layout.row(align=True)
            row.enabled = False
            row.operator("pipeline.check_publish", icon="VIEWZOOM")
            row.operator("pipeline.publish", icon="EXPORT")
            results.draw_results(layout)
            return
        box = layout.box()
        pair(box, "Node", chosen.root.name)
        pair(box, "Publishes", title)
        pair(box, "As", writes)
        if chosen.kind == "asset":
            layout.prop(context.window_manager, "pipeline_link_back")
        row = layout.row(align=True)
        row.operator("pipeline.check_publish", icon="VIEWZOOM")
        row.operator("pipeline.publish", icon="EXPORT")
        preview = review.current
        if preview is not None and (preview.title, preview.writes) == (title, writes):
            for fact in preview.facts:
                box.label(text=fact)
            if preview.shots:
                draw_shots(box, preview)
        elif results.last is None or not results.last.published:
            wrapped(layout, "Check runs the checks and shows what changes, writing nothing.")
        results.draw_results(layout)


def draw_shots(layout: bpy.types.UILayout, preview: review.Preview) -> None:
    """A row per shot: number, frames, cut, cast, and what changed; the chosen shot first."""
    grid = layout.grid_flow(row_major=True, columns=5, even_columns=False, align=True)
    for heading in ("Shot", "Frames", "Cut", "Cast", "Change"):
        cell = grid.row()
        cell.enabled = False
        cell.label(text=heading)
    for shot in preview.shots:
        chosen = shot.shot == preview.highlight
        grid.label(text=shot.shot, icon="RIGHTARROW_THIN" if chosen else "BLANK1")
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
