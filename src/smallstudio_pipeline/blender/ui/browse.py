"""The choices in the Open and New Workfile dialogs: kind -> entity -> task -> version.

Operators using these need `kind`, `entity` and `task` enum properties (and `version` for
Open), plus a hidden `existing_only` bool property: True to offer only tasks with workfiles.
"""

from __future__ import annotations

from typing import Any

import bpy

from ...core.entities import Asset, Entity
from .. import state

NONE = "NONE"
Items = list[tuple[str, str, str]]

# Blender garbles labels, or crashes, if the strings an items callback returns are
# garbage-collected, so each list is kept here until the next call replaces it.
_kept: dict[str, Items] = {}


def _keep(key: str, items: Items) -> Items:
    _kept[key] = items or [(NONE, "None", "Nothing to choose")]
    return _kept[key]


def kind_items(operator: Any, context: bpy.types.Context | None) -> Items:
    project = state.current.project
    kinds = project.kinds() if project else []
    return _keep("kind", [(kind, kind.title(), "") for kind in kinds])


def entity_items(operator: Any, context: bpy.types.Context | None) -> Items:
    project = state.current.project
    if project is None or operator.kind == NONE:
        return _keep("entity", [])
    names = [entity.name for entity in project.entities(operator.kind)]
    return _keep("entity", [(name, name, "") for name in names])


def task_items(operator: Any, context: bpy.types.Context | None) -> Items:
    entity = selected_entity(operator)
    if entity is None:
        return _keep("task", [])
    tasks = entity.tasks_with_workfiles() if operator.existing_only else entity.tasks
    return _keep("task", [(task, task.title(), "") for task in tasks])


def version_items(operator: Any, context: bpy.types.Context | None) -> Items:
    entity = selected_entity(operator)
    if entity is None or operator.task == NONE:
        return _keep("version", [])
    padding = entity.project.config.version_padding
    newest_first = reversed(entity.workfile_versions(operator.task))
    return _keep("version", [(str(v), f"v{v:0{padding}d}", "") for v in newest_first])


def selected_entity(operator: Any) -> Entity | None:
    project = state.current.project
    if project is None or NONE in (operator.kind, operator.entity):
        return None
    return project.entity(entity_kind(operator.kind), operator.entity)


def entity_kind(kind: str) -> str:
    """Map a browsing kind (an asset type, "sequence" or "shot") to an entity kind."""
    return kind if kind in ("sequence", "shot") else "asset"


# Changing a choice resets the ones after it to their first item.


def reset_entity(operator: Any, context: bpy.types.Context | None) -> None:
    operator.entity = entity_items(operator, context)[0][0]


def reset_task(operator: Any, context: bpy.types.Context | None) -> None:
    operator.task = task_items(operator, context)[0][0]


def reset_version(operator: Any, context: bpy.types.Context | None) -> None:
    if hasattr(operator, "version"):
        operator.version = version_items(operator, context)[0][0]


def preselect(operator: Any) -> None:
    """Start the dialog on the open file's entity and task, when there is one."""
    project, file = state.current.project, state.current.context
    if project is None or file is None:
        return
    entity = project.entity(file.entity_kind, file.entity)
    kind = entity.asset_type if isinstance(entity, Asset) else entity.kind
    operator.kind = kind
    operator.entity = entity.name
    if file.task in [item[0] for item in task_items(operator, bpy.context)]:
        operator.task = file.task
