"""Publishing's menu action: Publish.

Pipeline > Publish: check what the open workfile makes, then publish it.

In an asset's own workfile, a task that builds on another (a rig) first takes that
publish's materials, and the file is saved. Inside another asset's file, the asset is
moved into its own space, saved as its next workfile, published and linked back. In a
sequence's layout workfile, each shot is checked, the whole file is published, and the
cut (frame ranges, cut points, casting) goes into each shot's metadata. Everything is
checked with publish-validator first; a blocked publish lists its problems in the sidebar.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from publish_validator import Subject, Validator

from ...common.errors import PipelineError
from ...interface.common import has_project
from ...project.blender.identity import asset_identity, built_from
from ...project.core.entities import Sequence
from ...project.core.project import Project
from ...session import state
from ...shots.blender import layout
from ...shots.core.layout import apply_cut, check_cut
from ...workfiles.blender import workfiles
from ...workfiles.core.context import FileContext
from ..core.publishing import (
    Dependency,
    PublishTarget,
    new_record,
    plan_publish,
    publish_target,
    write_records,
)
from . import in_context, results, review
from . import layout as layout_publish
from .assets import dependencies, write_publish
from .materials import sync_materials
from .node import current_node, layout_sequence
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
                published = self.publish_asset(context, project, file, chosen.root)
            else:
                published = self.publish_layout(context, layout_sequence(project, file, chosen))
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        if published is None:
            return {"CANCELLED"}  # Blocked by checks; the sidebar says why.
        review.clear()  # What it would write has been written; Check again for the next.
        self.report({"INFO"}, f"Published {published}")
        return {"FINISHED"}

    def publish_asset(
        self, context: Context, project: Project, file: FileContext, root: Collection
    ) -> str | None:
        """Publish an asset's root, from its own workfile or in context."""
        identity = asset_identity(root)
        assert identity is not None  # An asset's node is its root.
        target = publish_target(project, file, identity[0])
        if target.in_context:
            return self.publish_in_context(context, root, target, file.entity)
        return self.publish_in_own_workfile(context, root, target, file.entity)

    def publish_in_own_workfile(
        self, context: Context, root: Collection, target: PublishTarget, file_entity: str
    ) -> str | None:
        """Publish an asset from its own workfile, saving the file first."""
        project = target.asset.project
        # A rig takes its model's latest materials, by object name, every publish.
        source = built_from(root)
        synced = None
        if source is not None and project.config.tasks[target.task].builds_on:
            synced = sync_materials(root, project.root / source.path)
        # Save first, so the record's source workfile is what was published.
        if synced is not None or workfiles.has_unsaved_changes():
            workfiles.save_changes()

        last = self.check_asset(context, root, target, file_entity)
        if last is None:
            return None
        published = self.write_files(root, target, last, Path(bpy.data.filepath), source)
        return f"{published} ({synced.summary})" if synced else published

    def publish_in_context(
        self, context: Context, root: Collection, target: PublishTarget, file_entity: str
    ) -> str | None:
        """Publish an asset worked on inside another asset's file, then link it back in."""
        asset = target.asset
        with in_context.in_asset_space(root, context.view_layer):
            last = self.check_asset(context, root, target, file_entity)
            if last is None:
                return None
            # The asset's own workfiles get this version too, so its history stays whole.
            workfile = asset.workfile_path(target.task, asset.next_workfile_version(target.task))
            in_context.save_asset_workfile(root, workfile, asset.project.config)
            published = self.write_files(root, target, last, workfile, None)
        in_context.swap_for_link(root, asset, asset.hero_path(target.task), context.scene)
        workfiles.save_changes()  # This file now links the new publish.
        return f"{published}; it's linked here now"

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
        record = new_record(
            plan,
            source=Path(bpy.data.filepath),
            blender=bpy.app.version_string,
            object_names=[],
            dependencies=layout_publish.dependencies(project),
            checks=last.statuses(),
        )
        write_records(plan, record)
        last.published = plan.label
        results.redraw()
        return f"{plan.label} ({changes.summary})"

    def check_asset(
        self, context: Context, root: Collection, target: PublishTarget, file_entity: str
    ) -> results.LastPublish | None:
        """Check an asset. Returns None, with the results in the sidebar, if they block."""
        subject = subject_for(root, target, file_entity)
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
        source_publish: Dependency | None,
    ) -> str:
        """Write the publish and its records. Returns e.g. "hero_model v004"."""
        plan = plan_publish(target.asset, target.task)
        write_publish(root, plan)
        record = new_record(
            plan,
            source=source,
            blender=bpy.app.version_string,
            object_names=[obj.name for obj in root.all_objects],
            dependencies=dependencies(root, plan),
            built_from=source_publish,
            checks=last.statuses(),
        )
        write_records(plan, record)
        last.published = plan.label
        results.redraw()
        return last.published


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
