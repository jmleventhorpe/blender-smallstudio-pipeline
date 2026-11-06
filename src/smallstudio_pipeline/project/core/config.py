"""Project settings: the add-on's defaults.toml, overridden by a project's pipeline.toml.

load_config() merges the two, table by table, and checks every setting on load, so a
mistake in pipeline.toml is reported once with the file and setting named. The result is
a Config of plain dataclasses: a Task says which entity it belongs to, whether it
publishes, where it renders and which task it builds on; an AssetType lists its tasks, which
are optional and which task's publish shots link. Everything else reads settings here.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...common.errors import ConfigError, PipelineError
from ...common.reading import get, get_names

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
    builds_on: str | None = None  # A task whose latest publish this one takes materials from.


@dataclass(frozen=True)
class AssetType:
    name: str
    tasks: tuple[str, ...]
    optional_tasks: tuple[str, ...]
    shot_link: tuple[str, ...]  # Shots link the first of these the asset has.
    mark_children: bool = False  # Publish marks each child collection as an asset (a kit).

    @property
    def required_tasks(self) -> tuple[str, ...]:
        """The tasks every asset of this type has."""
        return tuple(task for task in self.tasks if task not in self.optional_tasks)

    def task_list(self, tasks: Iterable[str] = ()) -> list[str]:
        """Return the required tasks plus `tasks`, in this type's order."""
        chosen = {*self.required_tasks, *tasks}
        unknown = sorted(chosen - set(self.tasks))
        if unknown:
            raise PipelineError(f"{self.name} assets don't have a {unknown[0]} task.")
        return [task for task in self.tasks if task in chosen]


@dataclass(frozen=True)
class Config:
    fps: int
    resolution: tuple[int, int]
    episodes: bool
    render_root: str
    asset_library: str  # The folder registered as an Asset Browser library.
    shot_start: int  # The frame each shot's scene starts on.
    name_pattern: str
    version_padding: int
    code_step: int
    tasks: dict[str, Task]
    asset_types: dict[str, AssetType]
    templates: dict[str, str]
    render_templates: dict[str, str]


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
    try:
        return _build(data)
    except ValueError as error:
        raise ConfigError(f"{error}.") from None


def _build(data: dict[str, Any]) -> Config:
    project = get(data, "project", dict)
    naming = get(data, "naming", dict)

    name_pattern = get(naming, "name_pattern", str, "naming")
    try:
        re.compile(name_pattern)
    except re.error as error:
        raise ValueError(f"naming.name_pattern isn't a valid pattern: {error}") from None

    tasks = {name: _task(name, table) for name, table in get(data, "tasks", dict).items()}
    for task in tasks.values():
        _check_builds_on(task, tasks)
    asset_types = {
        name: _asset_type(name, table, tasks)
        for name, table in get(data, "asset_types", dict).items()
    }
    for kind, names in (("task", tasks), ("asset type", asset_types)):
        for name in names:
            if not re.fullmatch(name_pattern, name):
                raise ValueError(f"The {kind} name '{name}' doesn't match naming.name_pattern")

    return Config(
        fps=_positive(project, "fps", "project"),
        resolution=_resolution(project),
        episodes=get(project, "episodes", bool, "project"),
        render_root=get(project, "render_root", str, "project"),
        asset_library=get(project, "asset_library", str, "project"),
        shot_start=_positive(project, "shot_start", "project", minimum=0),
        name_pattern=name_pattern,
        version_padding=_positive(naming, "version_padding", "naming"),
        code_step=_positive(naming, "code_step", "naming", minimum=2),
        tasks=tasks,
        asset_types=asset_types,
        templates=_templates(data, "templates", REQUIRED_TEMPLATES),
        render_templates=_templates(data, "render_templates", REQUIRED_RENDER_TEMPLATES),
    )


def _task(name: str, table: Any) -> Task:
    where = f"tasks.{name}"
    entity = get(table, "entity", str, where)
    if entity not in ENTITIES:
        raise ValueError(f"{where}.entity should be one of {', '.join(ENTITIES)}, not '{entity}'")
    renders = get(table, "renders", str, where, default=None)
    if renders not in (None, "sequence", "shot"):
        raise ValueError(f"{where}.renders should be 'sequence' or 'shot', not '{renders}'")
    publishes = get(table, "publishes", bool, where, default=False)
    builds_on = get(table, "builds_on", str, where, default=None)
    return Task(name, entity, publishes, renders, builds_on)


def _check_builds_on(task: Task, tasks: dict[str, Task]) -> None:
    if task.builds_on is None:
        return
    upstream = tasks.get(task.builds_on)
    if upstream is None or upstream.entity != task.entity or not upstream.publishes:
        raise ValueError(
            f"tasks.{task.name}.builds_on: '{task.builds_on}' isn't a publishing {task.entity} task"
        )


def _asset_type(name: str, table: Any, tasks: dict[str, Task]) -> AssetType:
    where = f"asset_types.{name}"
    if name in ENTITIES:
        raise ValueError(f"'{name}' can't be an asset type name; it's used for {name}s")
    asset_tasks = get_names(table, "tasks", where)
    if not asset_tasks:
        raise ValueError(f"{where}.tasks needs at least one task")
    for task in asset_tasks:
        if task not in tasks or tasks[task].entity != "asset":
            raise ValueError(f"{where}.tasks: '{task}' isn't an asset task in [tasks]")
    optional = get_names(table, "optional_tasks", where, default=[])
    shot_link = get_names(table, "shot_link", where)
    for key, names in (("optional_tasks", optional), ("shot_link", shot_link)):
        for task in names:
            if task not in asset_tasks:
                raise ValueError(f"{where}.{key}: '{task}' isn't one of {name}'s tasks")
    if all(task in optional for task in shot_link):
        raise ValueError(f"{where}.shot_link needs at least one task that isn't optional")
    mark_children = get(table, "mark_children", bool, where, default=False)
    return AssetType(name, tuple(asset_tasks), tuple(optional), tuple(shot_link), mark_children)


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} isn't valid TOML: {error}.") from None


def _positive(table: dict[str, Any], key: str, where: str, minimum: int = 1) -> int:
    value = get(table, key, int, where)
    if value < minimum:
        raise ValueError(f"{where}.{key} should be at least {minimum}, not {value}")
    return value


def _resolution(project: dict[str, Any]) -> tuple[int, int]:
    value = get(project, "resolution", list, "project")
    if len(value) != 2 or not all(
        isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in value
    ):
        raise ValueError(f"project.resolution should be [width, height], not {value!r}")
    return value[0], value[1]


def _templates(data: dict[str, Any], key: str, required: tuple[str, ...]) -> dict[str, str]:
    table = get(data, key, dict)
    for name in table:
        get(table, name, str, key)
    missing = [name for name in required if name not in table]
    if missing:
        raise ValueError(f"[{key}] is missing {', '.join(missing)}")
    return dict(table)
