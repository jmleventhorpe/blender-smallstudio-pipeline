"""The last publish's check results, in the 3D viewport's sidebar (Pipeline tab).

results.last holds what the last publish checked and the validator that did it: one
report for an asset, or one per shot for a layout publish. The panel lists failed,
warning and fixed checks with their issues, under each shot's code when there are
several; Select picks an issue's objects (showing that shot's scene), and Fix runs a
check's fix and checks again.
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
class Checked:
    """One subject's results: the asset, or one shot of a layout publish."""

    label: str  # e.g. "010_010_0010", or "" for an asset.
    report: Report
    subject: Subject


@dataclass
class LastPublish:
    checked: list[Checked]
    validator: Validator  # Kept to select issues and run fixes.
    published: str | None = None  # e.g. "hero_rig v004", or None if it was blocked.

    @property
    def passed(self) -> bool:
        """True when nothing blocks the publish."""
        return all(part.report.passed for part in self.checked)

    def summary(self) -> str:
        """e.g. "1 failed, 6 passed", or per shot: "010_010_0010: 1 failed"."""
        if len(self.checked) == 1:
            return self.checked[0].report.summary()
        blocked = [part for part in self.checked if not part.report.passed] or self.checked
        return "; ".join(f"{part.label}: {part.report.summary()}" for part in blocked)

    def statuses(self) -> dict[str, str]:
        """Each check's status, for the publish record; per shot as "010_010_0010/ShotCamera"."""
        found = {}
        for part in self.checked:
            prefix = f"{part.label}/" if part.label else ""
            found.update({prefix + r.check_id: r.status for r in part.report.results})
        return found


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
        layout = self.layout
        if last.published:
            layout.label(text=f"Published {last.published}", icon="CHECKMARK")
        else:
            row = layout.row()
            row.alert = True
            row.label(text=f"Blocked: {last.summary()}", icon="ERROR")
        for error in last.checked[0].report.load_errors:  # The same for every part.
            layout.label(text=f"Couldn't load {error.source}: {error.short_message}", icon="ERROR")

        for part_index, part in enumerate(last.checked):
            shown = [result for result in part.report.results if result.status in SHOWN]
            if shown and part.label:
                layout.label(text=part.label, icon="SCENE_DATA")
            for result in shown:
                draw_result(layout.box(), result, part_index)
        layout.operator("pipeline.publish", text="Publish Again", icon="EXPORT")


def draw_result(box: bpy.types.UILayout, result, part: int) -> None:
    """Draw one check's result: its status, its Fix button and its issues."""
    header = box.row()
    header.alert = result.status in (FAILED, ERRORED)
    header.label(text=result.label, icon=ICONS[result.status])
    if result.can_fix and result.status in (FAILED, WARNING):
        fix = header.operator("pipeline.fix_check", text="Fix")
        fix.part, fix.check_id = part, result.check_id
    if result.error:
        box.label(text=result.short_error)
    for index, issue in enumerate(result.issues[:MAX_ISSUES]):
        row = box.row()
        row.label(text=issue.message)
        if issue.targets:
            select = row.operator("pipeline.select_issue", text="", icon="RESTRICT_SELECT_OFF")
            select.part, select.check_id, select.index = part, result.check_id, index
    if len(result.issues) > MAX_ISSUES:
        box.label(text=f"… and {len(result.issues) - MAX_ISSUES} more")


class PIPELINE_OT_select_issue(bpy.types.Operator):
    """Select what this problem is about"""

    bl_idname = "pipeline.select_issue"
    bl_label = "Select"
    bl_options = {"INTERNAL", "UNDO"}

    part: IntProperty()
    check_id: StringProperty()
    index: IntProperty()

    def execute(self, context: bpy.types.Context) -> set[str]:
        checked = part_of(self.part)
        result = checked.report.get(self.check_id) if checked else None
        if checked is None or result is None or self.index >= len(result.issues):
            return {"CANCELLED"}
        scene = checked.subject.extras.get("scene")
        if isinstance(scene, bpy.types.Scene) and context.window:
            context.window.scene = scene  # Show the shot the problem is in.
        assert last is not None  # part_of found a part.
        last.validator.select(result.issues[self.index].targets)
        return {"FINISHED"}


class PIPELINE_OT_fix_check(bpy.types.Operator):
    """Fix this check's problems automatically, then check again"""

    bl_idname = "pipeline.fix_check"
    bl_label = "Fix"
    bl_options = {"INTERNAL", "UNDO"}

    part: IntProperty()
    check_id: StringProperty()

    def execute(self, context: bpy.types.Context) -> set[str]:
        checked = part_of(self.part)
        if last is None or checked is None:
            return {"CANCELLED"}
        checked.report.replace(last.validator.run_one(self.check_id, checked.subject, fix=True))
        redraw()
        return {"FINISHED"}


def part_of(index: int) -> Checked | None:
    """One part of the last publish's results, if it's still there."""
    if last is None or not 0 <= index < len(last.checked):
        return None
    return last.checked[index]


CLASSES = (PIPELINE_PT_results, PIPELINE_OT_select_issue, PIPELINE_OT_fix_check)
