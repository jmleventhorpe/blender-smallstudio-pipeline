"""The choices in the Open and New Workfile dialogs: category -> entity -> task -> version.

A category is an asset type, "sequence" or "shot". Operators using these need `category`,
`entity` and `task` enum properties (and `version` for Open), plus a hidden
`existing_only` bool property: True to offer only tasks with workfiles.
"""

from __future__ import annotations

from typing import Any

import bpy

from ...core.entities import Asset, Entity, Sequence
from .. import state

NONE = "NONE"
NEW = "NEW"
Items = list[tuple[str, str, str]]

# Blender garbles labels, or crashes, if the strings an items callback returns are
# garbage-collected, so each list is kept here until the next call replaces it.
_kept: dict[str, Items] = {}


def _keep(key: str, items: Items) -> Items:
    _kept[key] = items or [(NONE, "None", "Nothing to choose")]
    return _kept[key]


def category_items(operator: Any, context: bpy.types.Context | None) -> Items:
    """The asset types, then Sequence and Shot."""
    project = state.current.project
    categories = project.categories() if project else []
    return _keep("category", [(name, name.title(), "") for name in categories])


def entity_items(operator: Any, context: bpy.types.Context | None) -> Items:
    """The names of the chosen category's entities."""
    project = state.current.project
    if project is None or operator.category == NONE:
        return _keep("entity", [])
    items = []
    for entity in project.entities_in(operator.category):
        title = entity.title if isinstance(entity, Sequence) else ""
        items.append((entity.name, f"{entity.name}  {title}" if title else entity.name, title))
    return _keep("entity", items)


def task_items(operator: Any, context: bpy.types.Context | None) -> Items:
    """The chosen entity's tasks: only those with workfiles, if existing_only."""
    entity = selected_entity(operator)
    if entity is None:
        return _keep("task", [])
    tasks = entity.tasks_with_workfiles() if operator.existing_only else entity.tasks
    return _keep("task", [(task, task.title(), "") for task in tasks])


def version_items(operator: Any, context: bpy.types.Context | None) -> Items:
    """The chosen task's workfile versions, newest first."""
    entity = selected_entity(operator)
    if entity is None or operator.task == NONE:
        return _keep("version", [])
    padding = entity.project.config.version_padding
    newest_first = reversed(entity.workfile_versions(operator.task))
    return _keep("version", [(str(v), f"v{v:0{padding}d}", "") for v in newest_first])


def selected_entity(operator: Any) -> Entity | None:
    """The entity chosen in the dialog, or None."""
    project = state.current.project
    if project is None or NONE in (operator.category, operator.entity):
        return None
    return project.entity(entity_kind(operator.category), operator.entity)


def entity_kind(category: str) -> str:
    """The entity kind for a category: "asset" for an asset type, else the category."""
    return category if category in ("sequence", "shot") else "asset"


# Changing a choice resets the ones after it to their first item.


def reset_entity(operator: Any, context: bpy.types.Context | None) -> None:
    operator.entity = entity_items(operator, context)[0][0]


def reset_task(operator: Any, context: bpy.types.Context | None) -> None:
    operator.task = task_items(operator, context)[0][0]


def reset_version(operator: Any, context: bpy.types.Context | None) -> None:
    if hasattr(operator, "version"):
        operator.version = version_items(operator, context)[0][0]


def episode_items(operator: Any, context: bpy.types.Context | None) -> Items:
    """The project's episodes, then a new one."""
    project = state.current.project
    if project is None:
        return _keep("episode", [])
    items = [(code, f"Episode {code}", "") for code in project.episodes()]
    new = project.next_episode()
    return _keep("episode", [*items, (NEW, f"New episode ({new})", "Start the next episode")])


def preselect(operator: Any) -> None:
    """Start the dialog on the open file's entity and task, when there is one."""
    project, file = state.current.project, state.current.context
    if project is None or file is None:
        return
    entity = project.entity(file.entity_kind, file.entity)
    operator.category = entity.asset_type if isinstance(entity, Asset) else entity.kind
    operator.entity = entity.name
    if file.task in [item[0] for item in task_items(operator, bpy.context)]:
        operator.task = file.task
