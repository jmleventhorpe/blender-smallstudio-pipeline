from __future__ import annotations

from pathlib import Path

import bpy

from ...core.errors import PipelineError
from ...core.publishing import new_record, plan_publish, publish_target, write_records
from .. import results, state, workfiles
from ..identity import asset_identity, built_from
from ..materials import sync_materials
from ..publish import dependencies, pick_root, write_publish
from ..validation import subject_for, validator_for
from .common import has_project


class PIPELINE_OT_publish(bpy.types.Operator):
    """Check the asset, then publish it: a new version, and the latest for shots to link"""

    bl_idname = "pipeline.publish"
    bl_label = "Publish"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if not has_project(cls):
            return False
        if state.current.context is None or state.current.context.is_publish:
            cls.poll_message_set("Open a pipeline workfile to publish from it.")
            return False
        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        project, file = state.current.project, state.current.context
        assert project is not None and file is not None  # Checked by poll.
        try:
            root = pick_root(context)
            identity = asset_identity(root)
            assert identity is not None  # pick_root only returns asset roots.
            target = publish_target(project, file, identity[0])
            if target.in_context:
                raise PipelineError(
                    f"Publishing {target.asset.name} from inside another asset's file "
                    "isn't supported yet. Publish it from its own workfile."
                )
            # A rig takes its model's latest materials, by object name, every publish.
            source = built_from(root)
            synced = None
            if source is not None and project.config.tasks[target.task].builds_on:
                synced = sync_materials(root, project.root / source.path)
            # Save first, so the record's source workfile is what was published.
            if synced is not None or workfiles.has_unsaved_changes():
                workfiles.save_changes()

            validator = validator_for(project)
            subject = subject_for(root, target, file.entity)
            report = validator.run(subject)
            last = results.LastPublish(report, subject, validator)
            if not report.passed:
                results.store(last)
                results.show_sidebar(context)
                self.report(
                    {"ERROR"}, f"Publish blocked ({report.summary()}). See Pipeline in the sidebar."
                )
                return {"CANCELLED"}

            plan = plan_publish(target.asset, target.task)
            write_publish(root, plan)
            record = new_record(
                plan,
                source=Path(bpy.data.filepath),
                blender=bpy.app.version_string,
                object_names=[obj.name for obj in root.all_objects],
                dependencies=dependencies(root, plan),
                built_from=source,
                checks={result.check_id: result.status for result in report.results},
            )
            write_records(plan, record)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        last.published = f"{plan.hero.stem} v{plan.version:03d}"
        results.store(last)
        details = f" ({synced.summary})" if synced else ""
        self.report({"INFO"}, f"Published {last.published}{details}")
        return {"FINISHED"}
