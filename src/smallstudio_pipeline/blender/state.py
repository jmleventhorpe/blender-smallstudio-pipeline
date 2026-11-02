"""What the open file is, worked out once per load or save so drawing the UI stays cheap."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import bpy

from ..core.context import FileContext, file_context
from ..core.entities import Project
from ..core.errors import PipelineError
from .preferences import active_project_root


@dataclass
class Current:
    project: Project | None = None
    context: FileContext | None = None
    label: str = "No project"
    warning: str | None = None  # Shown in the warning colour and as a tooltip.


current = Current()


def refresh() -> None:
    """Work out the open file's project and context again. Call after loading or saving."""
    global current
    current = describe(bpy.data.filepath, active_project_root())


def describe(filepath: str, fallback_root: Path | None) -> Current:
    """Describe a file: its project (or the fallback when it has none) and what it is."""
    path = Path(filepath) if filepath else None
    try:
        project = Project.find(path) if path else None
        if project is None and fallback_root is not None:
            project = Project(fallback_root)
    except PipelineError as error:  # A broken pipeline.toml shouldn't break the UI.
        return Current(label="Project error", warning=str(error))

    if project is None:
        return Current()
    name = project.root.name
    if path is None:
        return Current(project, label=f"{name} · unsaved file")
    context = file_context(project, path)
    if context is None:
        return Current(project, label=f"{name} · not a pipeline file", warning=UNMANAGED)
    warning = PUBLISH if context.is_publish else None
    return Current(project, context, context.label, warning)


UNMANAGED = "This file isn't a pipeline workfile. Use Pipeline > Open or New Workfile."
PUBLISH = "This is a publish. Changes here won't reach shots; open the workfile instead."
