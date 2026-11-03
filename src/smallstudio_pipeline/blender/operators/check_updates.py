"""Pipeline > Check Updates: reload linked publishes that were published again, and say
which, along with anything built from an older publish.
"""

from __future__ import annotations

import bpy

from .. import state, updates
from .common import has_project


class PIPELINE_OT_check_updates(bpy.types.Operator):
    """Reload linked publishes that have been published again since this file opened"""

    bl_idname = "pipeline.check_updates"
    bl_label = "Check Updates"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        assert project is not None  # Checked by poll.
        changes = updates.reload_changed(project)
        stale = updates.stale_builds(project, context.scene)
        news = []
        if changes:
            news.append("Updated " + ", ".join(change.label for change in changes))
        if stale:
            news.append(updates.stale_warning(stale))
        self.report(
            {"WARNING" if stale else "INFO"}, ". ".join(news) or "Everything is up to date."
        )
        return {"FINISHED"}
