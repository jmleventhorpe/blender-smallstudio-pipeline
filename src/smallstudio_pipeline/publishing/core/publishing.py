"""What a publish is and what it records. Assets are written by publishing/blender/assets.py.

publish_target() says what publishing an asset node means: its asset and the node's task.
plan_publish() gives the next version and where its files go; PublishRecord is what's
written beside them, including the instances placed in it (a set's contents). Each
publish writes a versioned file and overwrites the hero file that other files link, each
with a JSON record of the same name:

    hero_rig_v004.blend   hero_rig_v004.json     this version, kept
    hero_rig.blend        hero_rig.json          always the latest
"""

from __future__ import annotations

import json
import socket
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ...common.errors import MetadataError, PipelineError
from ...common.files import write_atomic
from ...common.reading import get, get_names
from ...project.core.entities import Asset, Entity
from ...project.core.project import Project
from ...workfiles.core.inuse import current_user

SCHEMA = 1
_MANIFEST = Path(__file__).resolve().parents[2] / "blender_manifest.toml"  # The add-on's root.


@dataclass(frozen=True)
class PublishTarget:
    asset: Asset
    task: str


def publish_target(project: Project, asset_name: str, task: str) -> PublishTarget:
    """What publishing an asset node means: its asset, for the node's task."""
    asset = project.asset(asset_name)
    if not task:
        raise PipelineError(f"{asset.name}'s node has no task: set one in the Nodes panel.")
    if not asset.has_task(task):
        raise PipelineError(f"{asset.name} has no {task} task.")
    if not project.config.tasks[task].publishes:
        raise PipelineError(f"{task} doesn't publish.")
    return PublishTarget(asset, task)


@dataclass(frozen=True)
class PublishPlan:
    entity: Entity
    task: str
    version: int
    path: Path  # The versioned file.
    hero: Path  # The file other files link.

    @property
    def label(self) -> str:
        """e.g. "hero_model v004"."""
        padding = self.entity.project.config.version_padding
        return f"{self.hero.stem} v{self.version:0{padding}d}"

    @property
    def record(self) -> Path:
        """Where the versioned file's record goes."""
        return record_path(self.path)

    @property
    def hero_record(self) -> Path:
        """Where the hero file's record goes."""
        return record_path(self.hero)


def plan_publish(entity: Entity, task: str) -> PublishPlan:
    """The next publish of a task: its version and where its files go."""
    version = entity.next_publish_version(task)
    return PublishPlan(
        entity, task, version, entity.publish_path(task, version), entity.hero_path(task)
    )


def record_path(publish: Path) -> Path:
    """A publish's record sits beside it, with the same name."""
    return publish.with_suffix(".json")


@dataclass(frozen=True)
class Dependency:
    path: str  # A publish, relative to the project root.
    version: int | None  # Its version when it was used, if its record said.


@dataclass(frozen=True)
class Placement:
    """An instance placed in a published asset (a crate in a set): what, which, where."""

    asset: str
    instance_id: str
    location: tuple[float, float, float]
    rotation: tuple[float, float, float]  # XYZ Euler, in radians.
    scale: tuple[float, float, float]


@dataclass
class PublishRecord:
    entity: str  # "hero", or a sequence or shot code.
    entity_kind: str  # "asset", "sequence" or "shot"
    task: str
    version: int
    source: str  # The workfile it came from, relative to the project root.
    user: str
    machine: str
    published: datetime
    blender: str
    tool: str
    object_names: list[str] = field(default_factory=list)  # For the stable-names check.
    dependencies: list[Dependency] = field(default_factory=list)  # Linked publishes.
    instances: list[Placement] = field(default_factory=list)  # A set's contents, say.
    checks: dict[str, str] = field(default_factory=dict)  # Check name -> status.
    schema: int = SCHEMA

    def to_json(self) -> str:
        """The record as JSON text, as written beside the publish."""
        data = asdict(self)
        data["published"] = self.published.isoformat()
        return json.dumps(data, indent=2) + "\n"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PublishRecord:
        return cls(
            entity=get(data, "entity", str),
            # Records written before November 2026 call it "kind".
            entity_kind=get(data, "entity_kind" if "entity_kind" in data else "kind", str),
            task=get(data, "task", str),
            version=get(data, "version", int),
            source=get(data, "source", str),
            user=get(data, "user", str),
            machine=get(data, "machine", str),
            published=datetime.fromisoformat(get(data, "published", str)),
            blender=get(data, "blender", str),
            tool=get(data, "tool", str),
            object_names=get_names(data, "object_names", default=[]),
            dependencies=[
                _dependency(item) for item in get(data, "dependencies", list, default=[])
            ],
            instances=[_placement(item) for item in get(data, "instances", list, default=[])],
            checks=get(data, "checks", dict, default={}),
            schema=get(data, "schema", int, default=SCHEMA),
        )


def new_record(
    plan: PublishPlan,
    source: Path,
    blender: str,
    object_names: list[str],
    dependencies: list[Dependency] | None = None,
    instances: list[Placement] | None = None,
    checks: dict[str, str] | None = None,
) -> PublishRecord:
    """A record for a publish about to be written, with who, where and when filled in."""
    project = plan.entity.project
    return PublishRecord(
        entity=plan.entity.name,
        entity_kind=plan.entity.kind,
        task=plan.task,
        version=plan.version,
        source=relative(project, source),
        user=current_user(),
        machine=socket.gethostname(),
        published=datetime.now(UTC),
        blender=blender,
        tool=tool_version(),
        object_names=sorted(object_names),
        dependencies=dependencies or [],
        instances=sorted(instances or [], key=lambda placed: placed.instance_id),
        checks=checks or {},
    )


def write_records(plan: PublishPlan, record: PublishRecord) -> None:
    """Write the version's record and the hero's (the same record, for the latest)."""
    text = record.to_json()
    write_atomic(plan.record, text)
    write_atomic(plan.hero_record, text)


def read_record(path: Path) -> PublishRecord:
    """Read a publish record, or raise MetadataError saying what's wrong."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return PublishRecord.from_dict(data)
    except FileNotFoundError:
        raise MetadataError(f"{path} doesn't exist.") from None
    except (json.JSONDecodeError, ValueError) as error:
        raise MetadataError(f"{path}: {error}.") from None


def hero_record(entity: Entity, task: str) -> PublishRecord | None:
    """The record of a task's latest publish, or None if it has never published."""
    path = record_path(entity.hero_path(task))
    return read_record(path) if path.exists() else None


def builds_on_hero(asset: Asset, task: str) -> Path | None:
    """The hero file of the task this one builds on (a rig's model), if it's published."""
    upstream = asset.project.config.tasks[task].builds_on
    if upstream is None or not asset.has_task(upstream):
        return None
    hero = asset.hero_path(upstream)
    return hero if hero.exists() else None


def relative(project: Project, path: Path) -> str:
    """A path inside the project, relative to its root, with forward slashes."""
    return Path(path).resolve().relative_to(project.root).as_posix()


def tool_version() -> str:
    """The add-on's version, from its manifest."""
    with _MANIFEST.open("rb") as handle:
        return tomllib.load(handle)["version"]


def _dependency(data: Any) -> Dependency:
    return Dependency(get(data, "path", str), get(data, "version", int, default=None))


def _placement(data: Any) -> Placement:
    def triple(key: str) -> tuple[float, float, float]:
        values = get(data, key, list)
        if len(values) != 3 or not all(isinstance(v, int | float) for v in values):
            raise ValueError(f"instances.{key} should be three numbers, not {values!r}")
        return (float(values[0]), float(values[1]), float(values[2]))

    return Placement(
        get(data, "asset", str),
        get(data, "instance_id", str),
        triple("location"),
        triple("rotation"),
        triple("scale"),
    )
