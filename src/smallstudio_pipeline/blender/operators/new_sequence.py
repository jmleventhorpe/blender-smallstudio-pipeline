"""Pipeline > New Sequence: create a sequence and open its first layout workfile.

The sequence takes its episode's next number (or starts the next episode), with an
optional title shown beside its code. Its layout workfile opens with an empty cut.
"""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, StringProperty

from ...core.errors import PipelineError
from .. import state
from ..shots.layout import LAYOUT
from ..ui import browse
from ..workfiles import start_workfile
from .common import UnsavedChanges, has_project


class PIPELINE_OT_new_sequence(UnsavedChanges, bpy.types.Operator):
    """Create a sequence and open its layout workfile"""

    bl_idname = "pipeline.new_sequence"
    bl_label = "New Sequence"
    bl_options = {"REGISTER"}

    episode: EnumProperty(name="Episode", items=browse.episode_items)
    title: StringProperty(name="Title", description="What happens in it, e.g. Opening chase")

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        project = state.current.project
        if project is not None and project.config.episodes:
            self.layout.prop(self, "episode")
        self.layout.prop(self, "title")
        self.draw_unsaved(self.layout)

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        assert project is not None  # Checked by poll.
        try:
            episode = None
            if project.config.episodes:
                episode = project.next_episode() if self.episode == browse.NEW else self.episode
            self.handle_unsaved()
            sequence = project.create_sequence(episode, self.title)
            # Opening a file frees this operator, so nothing below may touch self.
            start_workfile(sequence, LAYOUT)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}
