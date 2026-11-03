"""Workfile decisions: where a new workfile goes, what it starts from, and versioning up.

The Blender operators do the opening and saving; the rules live here so they're testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .context import file_context
from .entities import Entity, Project
from .errors import PipelineError
from .publishing import Dependency, built_from


@dataclass(frozen=True)
class NewWorkfile:
    path: Path  # Where v001 is saved.
    starter: Path | None  # The .blend to start from, or None for an empty file.
    built_from: Dependency | None  # A publish to bring in (rig starts from the model).


def starter_file(project: Project, task: str) -> Path | None:
    """Return the task's starter file, or None if it has none."""
    starter = project.config.tasks[task].starter
    if starter is None:
        return None
    path = project.root / starter
    if not path.is_file():
        raise PipelineError(
            f"The {task} starter file {path} doesn't exist. "
            f"Fix tasks.{task}.starter in pipeline.toml."
        )
    return path


def new_workfile(entity: Entity, task: str) -> NewWorkfile:
    """Plan the first workfile for a task. Refuses if the task already has workfiles."""
    versions = entity.workfile_versions(task)
    if versions:
        latest = entity.workfile_path(task, versions[-1]).name
        raise PipelineError(f"{entity.label} already has {task} workfiles ({latest}); open it.")
    return NewWorkfile(
        entity.workfile_path(task, 1),
        starter_file(entity.project, task),
        built_from(entity, task),  # Raises if the publish to start from doesn't exist yet.
    )


def version_up_path(project: Project, current: Path) -> Path:
    """Return where Version Up saves the file at `current`: the task's next free version."""
    context = file_context(project, current)
    if context is None:
        raise PipelineError("This file isn't a pipeline workfile, so it can't be versioned up.")
    if context.is_publish:
        raise PipelineError("This is a publish, which is read-only. Open the workfile instead.")
    entity = project.entity(context.entity_kind, context.entity)
    # The next free version, not current + 1: someone may have saved a newer one.
    return entity.workfile_path(context.task, entity.next_workfile_version(context.task))
