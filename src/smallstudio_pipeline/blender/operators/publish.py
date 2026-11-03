"""Pipeline > Publish: check the asset holding the selection, then publish it.

In the asset's own workfile, a task that builds on another (a rig) first takes that
publish's materials, and the file is saved. Inside another asset's file, the asset is
moved into its own space, saved as its next workfile, published and linked back. Both
check with publish-validator first; a blocked publish lists its problems in the sidebar.
"""

from __future__ import annotations

from pathlib import Path

import bpy

from ...core.errors import PipelineError
from ...core.publishing import (
    Dependency,
    PublishTarget,
    new_record,
    plan_publish,
    publish_target,
    write_records,
)
from .. import in_context, state, workfiles
from ..identity import asset_identity, built_from
from ..materials import sync_materials
from ..publishing import dependencies, pick_root, write_publish
from ..ui import results
from ..validation import subject_for, validator_for
from .common import has_project

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
            root = pick_root(context)
            identity = asset_identity(root)
            assert identity is not None  # pick_root only returns asset roots.
            target = publish_target(project, file, identity[0])
            if target.in_context:
                published = self.publish_in_context(context, root, target, file.entity)
            else:
                published = self.publish_in_own_workfile(context, root, target, file.entity)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        if published is None:
            return {"CANCELLED"}  # Blocked by checks; the sidebar says why.
        self.report({"INFO"}, f"Published {published}")
        return {"FINISHED"}

    def publish_in_own_workfile(
        self, context: Context, root: Collection, target: PublishTarget, file_entity: str
    ) -> str | None:
        project = target.asset.project
        # A rig takes its model's latest materials, by object name, every publish.
        source = built_from(root)
        synced = None
        if source is not None and project.config.tasks[target.task].builds_on:
            synced = sync_materials(root, project.root / source.path)
        # Save first, so the record's source workfile is what was published.
        if synced is not None or workfiles.has_unsaved_changes():
            workfiles.save_changes()

        last = self.run_checks(context, root, target, file_entity)
        if last is None:
            return None
        published = self.write_files(root, target, last, Path(bpy.data.filepath), source)
        return f"{published} ({synced.summary})" if synced else published

    def publish_in_context(
        self, context: Context, root: Collection, target: PublishTarget, file_entity: str
    ) -> str | None:
        """Publish an asset worked on inside another asset's file, then link it back in."""
        asset = target.asset
        with in_context.in_asset_space(root):
            last = self.run_checks(context, root, target, file_entity)
            if last is None:
                return None
            # The asset's own workfiles get this version too, so its history stays whole.
            workfile = asset.workfile_path(target.task, asset.next_workfile_version(target.task))
            in_context.save_asset_workfile(root, workfile, asset.project.config)
            published = self.write_files(root, target, last, workfile, None)
        in_context.swap_for_link(root, asset, asset.hero_path(target.task))
        workfiles.save_changes()  # This file now links the new publish.
        return f"{published}; it's linked here now"

    def run_checks(
        self, context: Context, root: Collection, target: PublishTarget, file_entity: str
    ) -> results.LastPublish | None:
        """Run the checks. Returns None, with the results in the sidebar, if they block."""
        validator = validator_for(target.asset.project)
        subject = subject_for(root, target, file_entity)
        report = validator.run(subject)
        last = results.LastPublish(report, subject, validator)
        results.store(last)
        if not report.passed:
            results.show_sidebar(context)
            summary = report.summary()
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
            checks={result.check_id: result.status for result in last.report.results},
        )
        write_records(plan, record)
        last.published = f"{plan.hero.stem} v{plan.version:03d}"
        results.redraw()
        return last.published
