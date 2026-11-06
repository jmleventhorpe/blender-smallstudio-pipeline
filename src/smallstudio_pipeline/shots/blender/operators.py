"""Shots' menu actions: New Sequence, Add Shot and Omit Shot.

Pipeline > New Sequence: create a sequence and open its first layout workfile.

The sequence takes its episode's next number (or starts the next episode), with an
optional title shown beside its code. Its layout workfile opens with an empty cut.

Pipeline > Add Shot: add a shot to the cut, after the strip at the playhead.

The shot's folder and metadata are created straight away. Undoing removes its strip and
scene but not the shot; the next layout publish marks a shot with no strip omitted.

Pipeline > Omit Shot: take the selected shot's strip out of the cut.

The shot is marked omitted and keeps its number, folder and scene; nothing is deleted.
Adding a strip for its scene again brings it back at the next layout publish.
"""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, StringProperty

from ...common.errors import PipelineError
from ...interface import browse
from ...interface.common import UnsavedChanges, has_project, in_layout_workfile
from ...session import state
from ...workfiles.blender.workfiles import start_workfile
from . import layout
from .layout import LAYOUT


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


class PIPELINE_OT_add_shot(bpy.types.Operator):
    """Add a shot after the one at the playhead in the cut, with its own scene and camera"""

    bl_idname = "pipeline.add_shot"
    bl_label = "Add Shot"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls) and in_layout_workfile(cls)

    def execute(self, context: bpy.types.Context) -> set[str]:
        project, file = state.current.project, state.current.context
        assert project is not None and file is not None  # Checked by poll.
        try:
            master = layout.master_scene()
            shot = layout.add_shot(project.sequence(file.entity), master, master.frame_current)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Added shot {shot.name}")
        return {"FINISHED"}


def selected_shot_strip() -> bpy.types.SceneStrip | None:
    """The shot strip selected in the cut: the active one, or else the only one selected."""
    try:
        master = layout.master_scene()
    except PipelineError:
        return None
    selected = [strip for strip in layout.shot_strips(master) if strip.select]
    active = master.sequence_editor.active_strip
    for strip in selected:
        if strip == active:
            return strip
    return selected[0] if len(selected) == 1 else None


class PIPELINE_OT_omit_shot(bpy.types.Operator):
    """Take the selected shot out of the cut. Its scene and files stay"""

    bl_idname = "pipeline.omit_shot"
    bl_label = "Omit Shot"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not (has_project(cls) and in_layout_workfile(cls)):
            return False
        if selected_shot_strip() is None:
            showing = getattr(context, "sequencer_scene", None)
            master = layout.master_scene()
            if showing is not None and showing != master:
                cls.poll_message_set(
                    f"The Video Sequencer is showing {showing.name}. Set it to {master.name}, "
                    "the cut, in the sequencer's header."
                )
            else:
                cls.poll_message_set("Select one shot's strip in the cut (in the Video Sequencer).")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        project, file, strip = state.current.project, state.current.context, selected_shot_strip()
        assert project is not None and file is not None and strip is not None  # Checked by poll.
        try:
            shot = layout.omit_shot(strip, project.sequence(file.entity), layout.master_scene())
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Omitted shot {shot.name}. Its scene stays in this file.")
        return {"FINISHED"}


CLASSES = (
    PIPELINE_OT_new_sequence,
    PIPELINE_OT_add_shot,
    PIPELINE_OT_omit_shot,
)


class PIPELINE_OT_go_to_shot(bpy.types.Operator):
    """Show the selected shot's scene"""

    bl_idname = "pipeline.go_to_shot"
    bl_label = "Go to Shot"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if selected_shot_strip() is None:
            cls.poll_message_set("Select a shot's strip in the cut.")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        strip = selected_shot_strip()
        assert strip is not None and strip.scene is not None  # Checked by poll.
        return show_scene(self, context, strip.scene)


class PIPELINE_OT_back_to_cut(bpy.types.Operator):
    """Show the cut: the sequence's master scene"""

    bl_idname = "pipeline.back_to_cut"
    bl_label = "Back to Cut"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return in_layout_workfile(cls)

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            master = layout.master_scene()
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return show_scene(self, context, master)


def show_scene(
    operator: bpy.types.Operator, context: bpy.types.Context, scene: bpy.types.Scene
) -> set[str]:
    """Put a scene on show in the window."""
    if context.window is None:
        operator.report({"ERROR"}, "There's no window to show the scene in.")
        return {"CANCELLED"}
    context.window.scene = scene
    return {"FINISHED"}


CLASSES = (*CLASSES, PIPELINE_OT_go_to_shot, PIPELINE_OT_back_to_cut)
