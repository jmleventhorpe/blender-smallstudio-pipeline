"""The Pipeline tab in the sidebar, and the Context panel at its top.

Each job draws its own panels in the tab: Context here, then Shot (shots), Loaded
(loading), Publish (publishing) and Workfiles (workfiles), in that order (ORDER). Every
panel shows in both the 3D viewport's sidebar and the Video Sequencer's; Blender needs a
class for each, which both_sidebars() makes from one. A panel hides when it doesn't apply
to the open file.

Context says what the open file is, which shot or cut is on show, and every warning, with
Open, New Workfile and Version Up.
"""

from __future__ import annotations

import textwrap
from typing import Any

import bpy

from ..project.blender import nodes
from ..session import state
from ..shots.blender.layout import shot_number

TAB = "Pipeline"
SPACES = {"VIEW_3D": "view3d", "SEQUENCE_EDITOR": "sequencer"}
ORDER = {"context": 0, "nodes": 1, "shot": 2, "loaded": 3, "publish": 4, "workfiles": 5}
DASH = "\N{EN DASH}"  # Between the ends of a range of frames.
WRAP = 46  # Characters per line for messages: sidebar labels don't wrap themselves.


def both_sidebars(panel: type, name: str) -> tuple[type, ...]:
    """Panel classes for the 3D viewport's sidebar and the sequencer's, from one class."""
    return tuple(
        type(
            f"PIPELINE_PT_{name}_{suffix}",
            (panel, bpy.types.Panel),
            {
                "bl_space_type": space,
                "bl_region_type": "UI",
                "bl_category": TAB,
                "bl_order": ORDER[name],
            },
        )
        for space, suffix in SPACES.items()
    )


def redraw_sidebars() -> None:
    """Redraw the sidebars of every 3D viewport and sequencer, where the Pipeline tab is."""
    window_manager = bpy.context.window_manager
    for window in window_manager.windows if window_manager else ():
        for area in window.screen.areas:
            if area.type in SPACES:
                for region in area.regions:
                    if region.type == "UI":
                        region.tag_redraw()


def wrapped(layout: bpy.types.UILayout, text: str, icon: Any = "NONE", alert: bool = False) -> None:
    """A message over as many lines as it needs, with the icon on the first."""
    column = layout.column(align=True)
    column.alert = alert
    for index, line in enumerate(textwrap.wrap(text, WRAP) or [""]):
        column.label(text=line, icon=icon if index == 0 else "BLANK1")


def pair(layout: bpy.types.UILayout, name: str, value: str) -> None:
    """A "name  value" row, the name greyed."""
    row = layout.row()
    split = row.split(factor=0.3)
    label = split.row()
    label.enabled = False
    label.label(text=name)
    split.label(text=value)


class ContextPanel:
    """What the open file is, what's on show, and every warning."""

    bl_label = "Context"

    def draw(self: Any, context: bpy.types.Context) -> None:
        layout, current = self.layout, state.current
        project, file = current.project, current.context
        pair(layout, "Project", project.root.name if project else "None")
        if file is None:
            pair(layout, "File", current.label.rpartition(" · ")[2])
        else:
            pair(layout, "File", f"{file.entity} · {file.task}")
            version = "published" if file.version is None else f"v{file.version:0{file.padding}d}"
            pair(layout, "Version", f"{version} publish" if file.is_publish else version)
        shot = nodes.shot_node(context.scene)
        if shot is not None:
            pair(layout, "On show", f"shot {shot_number(shot.name)}")
        elif nodes.sequence_node(context.scene) is not None:
            pair(layout, "On show", "the cut")
        for warning in current.warnings:
            wrapped(layout.box(), warning, icon="ERROR", alert=True)
        if project is None:
            wrapped(layout, "Add a project in Preferences > Add-ons > Small Studio Pipeline.")
            return
        row = layout.row(align=True)
        row.operator("pipeline.open", text="Open…", icon="FILEBROWSER")
        row.operator("pipeline.save_to", text="Save To…", icon="FILE_TICK")
        row.operator("pipeline.version_up", text="Version Up", icon="DUPLICATE")


CLASSES = both_sidebars(ContextPanel, "context")
