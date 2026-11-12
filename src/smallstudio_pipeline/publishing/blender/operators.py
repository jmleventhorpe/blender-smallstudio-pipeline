"""Publishing's menu action: Publish.

Pipeline > Publish: check what the open workfile makes, then publish it.

In an asset's own workfile, a task that builds on another (a rig) first takes that
publish's materials, and the file is saved. Inside another asset's file, the asset is
moved into its own space, saved as its next workfile, published and linked back. In a
sequence's layout workfile, each shot is checked, the whole file is published, and the
cut (frame ranges, cut points, casting) goes into each shot's metadata. In its animation
workfile, each shot is checked (its cast against layout's too) and each shot's animation
node is published. Everything is checked with publish-validator first; a blocked publish
lists its problems in the sidebar.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from publish_validator import Subject, Validator

from ...common.errors import PipelineError
from ...interface.common import has_project
from ...loading.blender import editable
from ...project.blender.nodes import ANIM, LAYOUT, Node, current_node, node_sequence
from ...project.core.entities import Sequence
from ...project.core.project import Project
from ...session import state
from ...shots.blender import layout
from ...shots.core.layout import apply_cut, check_cut
from ...workfiles.blender import workfiles
from ..core.publishing import (
    Dependency,
    Placement,
    PublishPlan,
    PublishTarget,
    builds_on_hero,
    new_record,
    plan_publish,
    publish_target,
    write_records,
)
from . import animation as animation_publish
from . import layout as layout_publish
from . import results, review
from .assets import dependencies, placements, write_publish
from .materials import sync_materials
from .validation import subject_for, validator_for

Collection = bpy.types.Collection
Context = bpy.types.Context


class PIPELINE_OT_publish(bpy.types.Operator):
    """Check the asset, then publish it: a new version, and the latest for shots to link"""

    bl_idname = "pipeline.publish"
    bl_label = "Publish"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: Context) -> bool:
        if not has_project(cls):
            return False
        if state.current.context is None or state.current.context.is_publish:
            cls.poll_message_set("Open a pipeline workfile to publish from it.")
            return False
        return True

    def execute(self, context: Context) -> set[str]:
        project, file = state.current.project, state.current.context
        assert project is not None and file is not None  # Checked by poll.
        # Edit Mode changes only reach the mesh when leaving Edit Mode.
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            chosen = current_node(context)
            if chosen.kind == "asset":
                published = self.publish_asset(context, project, chosen)
            elif chosen.task == ANIM:
                published = self.publish_animation(context, node_sequence(project, chosen))
            elif chosen.task == LAYOUT:
                published = self.publish_layout(context, node_sequence(project, chosen))
            else:
                raise PipelineError(f"{chosen.task.title()} doesn't publish: render it instead.")
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        if published is None:
            return {"CANCELLED"}  # Blocked by checks; the sidebar says why.
        review.clear()  # What it would write has been written; Check again for the next.
        self.report({"INFO"}, f"Published {published}")
        return {"FINISHED"}

    def publish_asset(self, context: Context, project: Project, chosen: Node) -> str | None:
        """Publish an asset node as its task: in its own space, then linked back if asked."""
        target = publish_target(project, chosen.name, chosen.task)
        root = chosen.root
        # A rig takes its model's latest materials, by object name, every publish.
        model = builds_on_hero(target.asset, target.task)
        synced = sync_materials(root, model) if model is not None else None
        # Save first, so the record's source is this file as published.
        if not bpy.data.filepath:
            raise PipelineError(
                "Save this file first (Save To), so the publish can say where it came from."
            )
        workfiles.save_changes()
        with editable.in_asset_space(root, context.view_layer):  # Placed by Make Editable.
            last = self.check_asset(context, root, target)
            if last is None:
                return None
            placed = placements(root, context.scene, context.view_layer)
            published = self.write_files(root, target, last, Path(bpy.data.filepath), placed)
        if link_back_chosen(context):
            hero = target.asset.hero_path(target.task)
            editable.link_again(root, target.asset, hero, context.scene)
            workfiles.save_changes()  # This file now links the new publish.
            published += "; linked back here"
        return f"{published} ({synced.summary})" if synced else published

    def publish_layout(self, context: Context, sequence: Sequence) -> str | None:
        """Publish the sequence's layout: a copy of the whole file, and the cut into each shot."""
        project = sequence.project
        master = layout.master_scene()
        layout.sync_ranges(master)  # Retiming in the cut becomes each shot's range.
        check_cut(sequence, layout.cut(master, {}))
        # Save first: saving numbers new instances, and the record's source is this file.
        workfiles.save_changes()
        cuts = layout.cut(master, layout_publish.casting_by_shot(master))

        subjects = layout_publish.shot_subjects(master, project)
        last = self.run_checks(context, validator_for(project), subjects)
        if last is None:
            return None
        plan = plan_publish(sequence, layout.LAYOUT)
        layout_publish.write_layout(plan)
        changes = apply_cut(sequence, cuts)
        record_publish(plan, last, Path(bpy.data.filepath), layout_publish.dependencies(project))
        return f"{plan.label} ({changes.summary})"

    def publish_animation(self, context: Context, sequence: Sequence) -> str | None:
        """Publish the sequence's animation: each shot's animation node, for lighting."""
        project = sequence.project
        master = layout.master_scene()
        # Save first: saving numbers new instances, and the record's source is this file.
        workfiles.save_changes()
        subjects = layout_publish.shot_subjects(master, project, ANIM)
        last = self.run_checks(context, validator_for(project), subjects)
        if last is None:
            return None
        plan = plan_publish(sequence, ANIM)
        animation_publish.write_animation(plan, animation_publish.shot_roots(master))
        record_publish(plan, last, Path(bpy.data.filepath), layout_publish.dependencies(project))
        shots = len(subjects)
        return f"{plan.label} ({shots} shot{'s' if shots != 1 else ''})"

    def check_asset(
        self, context: Context, root: Collection, target: PublishTarget
    ) -> results.LastPublish | None:
        """Check an asset. Returns None, with the results in the sidebar, if they block."""
        subject = subject_for(root, target)
        return self.run_checks(context, validator_for(target.asset.project), [("", subject)])

    def run_checks(
        self, context: Context, validator: Validator, subjects: list[tuple[str, Subject]]
    ) -> results.LastPublish | None:
        """Check each subject. Returns None, with the sidebar showing why, if any block."""
        checked = [
            results.Checked(label, validator.run(subject), subject) for label, subject in subjects
        ]
        last = results.LastPublish(checked, validator)
        results.store(last)
        if not last.passed:
            results.show_sidebar(context)
            summary = last.summary()
            self.report({"ERROR"}, f"Publish blocked ({summary}). See Pipeline in the sidebar.")
            return None
        return last

    def write_files(
        self,
        root: Collection,
        target: PublishTarget,
        last: results.LastPublish,
        source: Path,
        placed: list[Placement],
    ) -> str:
        """Write the publish and its records. Returns e.g. "hero_model v004"."""
        plan = plan_publish(target.asset, target.task)
        write_publish(root, plan)
        names = [obj.name for obj in root.all_objects]
        record_publish(plan, last, source, dependencies(root, plan), names, placed)
        return plan.label


def record_publish(
    plan: PublishPlan,
    last: results.LastPublish,
    source: Path,
    depends_on: list[Dependency],
    object_names: list[str] | None = None,
    placed: list[Placement] | None = None,
) -> None:
    """Write a publish's records, and show it as published in the sidebar."""
    record = new_record(
        plan,
        source=source,
        blender=bpy.app.version_string,
        object_names=object_names or [],
        dependencies=depends_on,
        instances=placed or [],
        checks=last.statuses(),
    )
    write_records(plan, record)
    last.published = plan.label
    results.redraw()


def link_back_chosen(context: Context) -> bool:
    """Whether the Publish panel's Link Back box is ticked."""
    return bool(getattr(context.window_manager, "pipeline_link_back", False))


class PIPELINE_OT_check_publish(bpy.types.Operator):
    """See what Publish would write, and run its checks. Nothing is written"""

    bl_idname = "pipeline.check_publish"
    bl_label = "Check"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return PIPELINE_OT_publish.poll(context)

    def execute(self, context: Context) -> set[str]:
        project, file = state.current.project, state.current.context
        assert project is not None and file is not None  # Checked by poll.
        if context.mode != "OBJECT":  # Edit Mode changes only reach the mesh outside it.
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            last = review.review(context, project, file)
        except PipelineError as error:
            review.clear()
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        results.show_sidebar(context)
        if last.passed:
            self.report({"INFO"}, f"Checks pass ({last.summary()}).")
        else:
            self.report({"WARNING"}, f"Publish would be blocked ({last.summary()}).")
        return {"FINISHED"}


CLASSES = (PIPELINE_OT_publish, PIPELINE_OT_check_publish)
