"""What the open file is, worked out once per load or save so drawing the UI stays cheap.

state.current holds the project (from the file's path, or else the active project in the
preferences), the file's context, the top-bar label and any warning. refresh() rebuilds
it; the load and save handlers call it, and the menu, top bar and operators only read it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import bpy

from ..core.context import FileContext, file_context
from ..core.errors import PipelineError
from ..core.project import Project
from .ui.preferences import active_project_root

UNMANAGED = "This file isn't a pipeline workfile. Use Pipeline > Open or New Workfile."
PUBLISH = "This is a publish. Changes here won't reach shots; open the workfile instead."


@dataclass
class Current:
    project: Project | None = None
    context: FileContext | None = None
    label: str = "No project"
    # Shown in the Pipeline menu, with the top bar's label in the warning colour.
    warnings: list[str] = field(default_factory=list)


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
        return Current(label="Project error", warnings=[str(error)])

    if project is None:
        return Current()
    name = project.root.name
    if path is None:
        return Current(project, label=f"{name} · unsaved file")
    context = file_context(project, path)
    if context is None:
        return Current(project, label=f"{name} · not a pipeline file", warnings=[UNMANAGED])
    warnings = [PUBLISH] if context.is_publish else []
    return Current(project, context, context.label, warnings)
