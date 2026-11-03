"""Pieces the pipeline's operators share.

has_project() greys an operator out, with the reason as its tooltip, when there's no
project. UnsavedChanges asks what to do with the open file's unsaved changes before an
operator replaces that file.
"""

from __future__ import annotations

from typing import Any

import bpy
from bpy.props import EnumProperty

from .. import state, workfiles

NO_PROJECT = (
    "No project. Open a file inside a project, or add one in "
    "Preferences > Add-ons > Small Studio Pipeline."
)


def has_project(operator_class: Any) -> bool:
    """Poll check: greys the menu item out, with the reason as its tooltip."""
    if state.current.project is None:
        operator_class.poll_message_set(NO_PROJECT)
        return False
    return True


class UnsavedChanges:
    """For operators that replace the open file: asks what to do with unsaved changes."""

    unsaved: EnumProperty(
        name="Unsaved Changes",
        items=[
            ("SAVE", "Save Them", "Save the open file first"),
            ("DISCARD", "Don't Save", "Lose the changes to the open file"),
        ],
        default="SAVE",
    )

    def draw_unsaved(self, layout: bpy.types.UILayout | None) -> None:
        """Ask about unsaved changes in the dialog, if there are any."""
        if workfiles.has_unsaved_changes():
            layout.separator()
            layout.label(text="The open file has unsaved changes:", icon="ERROR")
            layout.prop(self, "unsaved", expand=True)

    def handle_unsaved(self) -> None:
        """Save the open file first, if it has changes and the artist chose to."""
        if workfiles.has_unsaved_changes() and self.unsaved == "SAVE":
            workfiles.save_changes()
