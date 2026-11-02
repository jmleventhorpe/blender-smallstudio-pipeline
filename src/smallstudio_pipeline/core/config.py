"""Project config: the built-in defaults, overridden by pipeline.toml at the project root."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigError

DEFAULTS = Path(__file__).resolve().parent.parent / "defaults.toml"
PROJECT_FILE = "pipeline.toml"
ENTITIES = ("asset", "sequence", "shot")
REQUIRED_TEMPLATES = tuple(
    f"{entity}_{kind}" for entity in ENTITIES for kind in ("metadata", "work", "publish", "hero")
)
REQUIRED_RENDER_TEMPLATES = ("sequence_render", "shot_render")


@dataclass(frozen=True)
class Task:
    name: str
    entity: str  # What its workfiles belong to: "asset", "sequence" or "shot".
    publishes: bool
    renders: str | None  # Where its renders go: "sequence", "shot", or None.


@dataclass(frozen=True)
class AssetType:
    name: str
    tasks: tuple[str, ...]
    optional_tasks: tuple[str, ...]
    shot_link: tuple[str, ...]  # Shots link the first of these the asset has.

    @property
    def required_tasks(self) -> tuple[str, ...]:
        return tuple(task for task in self.tasks if task not in self.optional_tasks)


@dataclass(frozen=True)
class Config:
    fps: int
    resolution: tuple[int, int]
    episodes: bool
    render_root: str
    name_pattern: str
    version_padding: int
    code_step: int
    tasks: dict[str, Task]
    asset_types: dict[str, AssetType]
    templates: dict[str, str]
    render_templates: dict[str, str]

    def task_names(self, entity: str) -> list[str]:
        """Return the names of the tasks whose workfiles belong to an entity kind."""
        return [task.name for task in self.tasks.values() if task.entity == entity]


def load_config(project_root: Path | None = None) -> Config:
    """Load the defaults, merged with the project's pipeline.toml when there is one."""
    data = _read_toml(DEFAULTS)
    project_file = Path(project_root) / PROJECT_FILE if project_root is not None else None
    if project_file is None or not project_file.is_file():
        return build_config(data)
    try:
        return build_config(merge(data, _read_toml(project_file)))
    except ConfigError as error:
        raise ConfigError(f"{project_file}: {error}") from None


def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override into base: tables merge key by key, anything else replaces."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_config(data: dict[str, Any]) -> Config:
    """Check the merged settings and turn them into a Config, or raise ConfigError."""
    project = _table(data, "project")
    naming = _table(data, "naming")

    name_pattern = _value(naming, "name_pattern", str, "naming")
    try:
        re.compile(name_pattern)
    except re.error as error:
        raise ConfigError(f"naming.name_pattern isn't a valid pattern: {error}.") from None

    tasks = {
        name: _task(name, _value(_table(data, "tasks"), name, dict, "tasks"))
        for name in _table(data, "tasks")
    }
    asset_types = {
        name: _asset_type(
            name, _value(_table(data, "asset_types"), name, dict, "asset_types"), tasks
        )
        for name in _table(data, "asset_types")
    }
    for kind, names in (("task", tasks), ("asset type", asset_types)):
        for name in names:
            if not re.fullmatch(name_pattern, name):
                raise ConfigError(f"The {kind} name '{name}' doesn't match naming.name_pattern.")

    templates = _string_table(data, "templates", REQUIRED_TEMPLATES)
    render_templates = _string_table(data, "render_templates", REQUIRED_RENDER_TEMPLATES)

    return Config(
        fps=_positive(project, "fps", "project"),
        resolution=_resolution(project),
        episodes=_value(project, "episodes", bool, "project"),
        render_root=_value(project, "render_root", str, "project"),
        name_pattern=name_pattern,
        version_padding=_positive(naming, "version_padding", "naming"),
        code_step=_positive(naming, "code_step", "naming", minimum=2),
        tasks=tasks,
        asset_types=asset_types,
        templates=templates,
        render_templates=render_templates,
    )


def _task(name: str, table: dict[str, Any]) -> Task:
    where = f"tasks.{name}"
    entity = _value(table, "entity", str, where)
    if entity not in ENTITIES:
        raise ConfigError(f"{where}.entity should be one of {', '.join(ENTITIES)}, not '{entity}'.")
    renders = _value(table, "renders", str, where, default=None)
    if renders not in (None, "sequence", "shot"):
        raise ConfigError(f"{where}.renders should be 'sequence' or 'shot', not '{renders}'.")
    publishes = _value(table, "publishes", bool, where, default=False)
    return Task(name, entity, publishes, renders)


def _asset_type(name: str, table: dict[str, Any], tasks: dict[str, Task]) -> AssetType:
    where = f"asset_types.{name}"
    asset_tasks = _strings(table, "tasks", where)
    if not asset_tasks:
        raise ConfigError(f"{where}.tasks needs at least one task.")
    for task in asset_tasks:
        if task not in tasks or tasks[task].entity != "asset":
            raise ConfigError(f"{where}.tasks: '{task}' isn't an asset task in [tasks].")
    optional = _strings(table, "optional_tasks", where, default=())
    shot_link = _strings(table, "shot_link", where)
    for key, names in (("optional_tasks", optional), ("shot_link", shot_link)):
        for task in names:
            if task not in asset_tasks:
                raise ConfigError(f"{where}.{key}: '{task}' isn't one of {name}'s tasks.")
    if all(task in optional for task in shot_link):
        raise ConfigError(f"{where}.shot_link needs at least one task that isn't optional.")
    return AssetType(name, asset_tasks, optional, shot_link)


# Readers that name the setting in their error messages.

_MISSING = object()
_KIND_NAMES = {int: "a whole number", bool: "true or false", str: "text", dict: "a table"}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} isn't valid TOML: {error}.") from None


def _value(table: dict[str, Any], key: str, kind: type, where: str, default: Any = _MISSING) -> Any:
    if key not in table:
        if default is _MISSING:
            raise ConfigError(f"{where}.{key} is missing.")
        return default
    value = table[key]
    # bool is a subclass of int in Python, so rule it out explicitly.
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ConfigError(f"{where}.{key} should be {_KIND_NAMES[kind]}, not {value!r}.")
    return value


def _table(data: dict[str, Any], key: str) -> dict[str, Any]:
    return _value(data, key, dict, "config")


def _positive(table: dict[str, Any], key: str, where: str, minimum: int = 1) -> int:
    value = _value(table, key, int, where)
    if value < minimum:
        raise ConfigError(f"{where}.{key} should be at least {minimum}, not {value}.")
    return value


def _resolution(project: dict[str, Any]) -> tuple[int, int]:
    value = project.get("resolution")
    if not (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in value)
    ):
        raise ConfigError(f"project.resolution should be [width, height], not {value!r}.")
    return value[0], value[1]


def _strings(
    table: dict[str, Any], key: str, where: str, default: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    if key not in table and default is not None:
        return default
    value = table.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{where}.{key} should be a list of names, not {value!r}.")
    return tuple(value)


def _string_table(data: dict[str, Any], key: str, required: tuple[str, ...]) -> dict[str, str]:
    table = _table(data, key)
    for name, value in table.items():
        if not isinstance(value, str):
            raise ConfigError(f"{key}.{name} should be text, not {value!r}.")
    missing = [name for name in required if name not in table]
    if missing:
        raise ConfigError(f"[{key}] is missing {', '.join(missing)}.")
    return dict(table)
