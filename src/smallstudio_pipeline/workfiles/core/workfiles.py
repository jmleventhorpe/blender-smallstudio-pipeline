"""Where workfiles go: the rules behind New Workfile, Save To and Version Up.

A workfile is only a file saved in the right place; what's in it is the artist's, and
the nodes in it say what it's working on. next_workfile_path() is the next free version
of an entity's task, which New Workfile and Save To use. version_up_path() is the open
workfile's next free version, which may be beyond current + 1 if someone else has saved
since. The Blender side is workfiles/blender/workfiles.py.
"""

from __future__ import annotations

from pathlib import Path

from ...common.errors import PipelineError
from ...project.core.entities import Entity
from ...project.core.project import Project
from .context import PUBLISH_IS_READ_ONLY, file_context


def next_workfile_path(entity: Entity, task: str) -> Path:
    """Where an entity's task's next workfile goes: its next free version."""
    return entity.workfile_path(task, entity.next_workfile_version(task))


def version_up_path(project: Project, current: Path) -> Path:
    """Return where Version Up saves the file at `current`: the task's next free version."""
    context = file_context(project, current)
    if context is None:
        raise PipelineError("This file isn't a pipeline workfile, so it can't be versioned up.")
    if context.is_publish:
        raise PipelineError(PUBLISH_IS_READ_ONLY)
    entity = project.entity(context.entity_kind, context.entity)
    # The next free version, not current + 1: someone may have saved a newer one.
    return next_workfile_path(entity, context.task)
