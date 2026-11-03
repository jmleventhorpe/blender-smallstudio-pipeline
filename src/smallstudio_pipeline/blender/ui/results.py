"""The last publish's check results, in the 3D viewport's sidebar (Pipeline tab).

results.last holds the report, the subject and the validator from the last publish. The
panel lists failed, warning and fixed checks with their issues; Select picks an issue's
objects, and Fix runs a check's fix and checks again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import bpy
from bpy.props import IntProperty, StringProperty
from publish_validator import ERRORED, FAILED, FIXED, WARNING, Report, Subject, Validator

SHOWN = (FAILED, ERRORED, WARNING, FIXED)  # Passed and skipped checks aren't listed.
ICONS: dict[str, Any] = {FAILED: "CANCEL", ERRORED: "ERROR", WARNING: "INFO", FIXED: "CHECKMARK"}
MAX_ISSUES = 12


@dataclass
class LastPublish:
    report: Report
    subject: Subject
    validator: Validator  # Kept to select issues and run fixes.
    published: str | None = None  # e.g. "hero_rig v004", or None if it was blocked.


last: LastPublish | None = None


def store(publish: LastPublish) -> None:
    """Keep a publish's results and redraw the sidebar."""
    global last
    last = publish
    redraw()


def clear() -> None:
    """Forget the last results."""
    global last
    last = None


def redraw() -> None:
    """Redraw every 3D viewport, so the sidebar shows the latest results."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def show_sidebar(context: bpy.types.Context) -> None:
    """Open the 3D viewport's sidebar, where the results are."""
    for area in context.screen.areas if context.screen else ():
        if area.type == "VIEW_3D":
            area.spaces.active.show_region_ui = True


class PIPELINE_PT_results(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Pipeline"
    bl_label = "Publish"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return last is not None

    def draw(self, context: bpy.types.Context) -> None:
        assert last is not None  # Checked by poll.
        layout, report = self.layout, last.report
        if last.published:
            layout.label(text=f"Published {last.published}", icon="CHECKMARK")
        else:
            row = layout.row()
            row.alert = True
            row.label(text=f"Blocked: {report.summary()}", icon="ERROR")
        for error in report.load_errors:
            layout.label(text=f"Couldn't load {error.source}: {error.short_message}", icon="ERROR")

        for result in report.results:
            if result.status in SHOWN:
                draw_result(layout.box(), result)
        layout.operator("pipeline.publish", text="Publish Again", icon="EXPORT")


def draw_result(box: bpy.types.UILayout, result) -> None:
    """Draw one check's result: its status, its Fix button and its issues."""
    header = box.row()
    header.alert = result.status in (FAILED, ERRORED)
    header.label(text=result.label, icon=ICONS[result.status])
    if result.can_fix and result.status in (FAILED, WARNING):
        header.operator("pipeline.fix_check", text="Fix").check_id = result.check_id
    if result.error:
        box.label(text=result.short_error)
    for index, issue in enumerate(result.issues[:MAX_ISSUES]):
        row = box.row()
        row.label(text=issue.message)
        if issue.targets:
            select = row.operator("pipeline.select_issue", text="", icon="RESTRICT_SELECT_OFF")
            select.check_id, select.index = result.check_id, index
    if len(result.issues) > MAX_ISSUES:
        box.label(text=f"… and {len(result.issues) - MAX_ISSUES} more")


class PIPELINE_OT_select_issue(bpy.types.Operator):
    """Select what this problem is about"""

    bl_idname = "pipeline.select_issue"
    bl_label = "Select"
    bl_options = {"INTERNAL", "UNDO"}

    check_id: StringProperty()
    index: IntProperty()

    def execute(self, context: bpy.types.Context) -> set[str]:
        result = last.report.get(self.check_id) if last else None
        if last is None or result is None or self.index >= len(result.issues):
            return {"CANCELLED"}
        last.validator.select(result.issues[self.index].targets)
        return {"FINISHED"}


class PIPELINE_OT_fix_check(bpy.types.Operator):
    """Fix this check's problems automatically, then check again"""

    bl_idname = "pipeline.fix_check"
    bl_label = "Fix"
    bl_options = {"INTERNAL", "UNDO"}

    check_id: StringProperty()

    def execute(self, context: bpy.types.Context) -> set[str]:
        if last is None:
            return {"CANCELLED"}
        last.report.replace(last.validator.run_one(self.check_id, last.subject, fix=True))
        redraw()
        return {"FINISHED"}


CLASSES = (PIPELINE_PT_results, PIPELINE_OT_select_issue, PIPELINE_OT_fix_check)
