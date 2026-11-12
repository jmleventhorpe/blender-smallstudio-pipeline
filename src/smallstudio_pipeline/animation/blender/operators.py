"""Animation's menu actions: Animate.

Pipeline > Animate: give the selection (a whole character, if part of one is selected)
its own copy of layout's keys, so it can be keyed here. See animate.py.
"""

from __future__ import annotations

import bpy

from ...interface.common import has_project
from . import animate


class PIPELINE_OT_animate(bpy.types.Operator):
    """Give the selection its own copy of layout's keys, to key it here. It stops following
    layout's keys"""

    bl_idname = "pipeline.animate"
    bl_label = "Animate"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not has_project(cls):
            return False
        selected = list(context.selected_objects or ())
        if not animate.to_animate(selected, context.scene):
            cls.poll_message_set("Nothing selected plays layout's keys: key it as it is.")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        objects = animate.to_animate(list(context.selected_objects or ()), context.scene)
        animate.animate(objects)
        names = ", ".join(obj.name for obj in objects)
        self.report({"INFO"}, f"{names}: key away. They no longer follow layout's keys.")
        return {"FINISHED"}


CLASSES = (PIPELINE_OT_animate,)
