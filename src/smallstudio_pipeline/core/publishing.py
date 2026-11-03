"""What a publish is and what it records. Assets are written by blender/assets/publishing.py.

publish_target() decides what publishing a root means: which asset and task, and whether
it's in context (a prop published from inside its set). plan_publish() gives the next
version and where its files go; PublishRecord is what's written beside them; built_from()
is the publish a task starts from. Each publish writes a versioned file and overwrites
the hero file that other files link, each with a JSON record of the same name:

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

from .context import PUBLISH_IS_READ_ONLY, FileContext
from .entities import Asset, Entity
from .errors import MetadataError, PipelineError
from .files import write_atomic
from .inuse import current_user
from .project import Project
from .reading import get, get_names

SCHEMA = 1
_MANIFEST = Path(__file__).resolve().parent.parent / "blender_manifest.toml"


@dataclass(frozen=True)
class PublishTarget:
    asset: Asset
    task: str
    in_context: bool  # The root isn't in its own asset's workfile, e.g. a prop in a set.


def publish_target(project: Project, file: FileContext | None, asset_name: str) -> PublishTarget:
    """Work out what publishing an asset's root from the open file means.

    In the asset's own workfile, it publishes that file's task. Anywhere else (a prop
    built inside a set, say) it publishes the asset's first task, which is how sets
    and their props are built.
    """
    if file is None:
        raise PipelineError("Save this file as a pipeline workfile before publishing from it.")
    if file.is_publish:
        raise PipelineError(PUBLISH_IS_READ_ONLY)
    asset = project.asset(asset_name)
    if file.entity_kind == "asset" and file.entity == asset.name:
        return PublishTarget(asset, file.task, in_context=False)
    return PublishTarget(asset, asset.tasks[0], in_context=True)


@dataclass(frozen=True)
class PublishPlan:
    entity: Entity
    task: str
    version: int
    path: Path  # The versioned file.
    hero: Path  # The file other files link.

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
    built_from: Dependency | None = None  # The publish a rig was built from.
    checks: dict[str, str] = field(default_factory=dict)  # Check name -> status.
    schema: int = SCHEMA

    def to_json(self) -> str:
        """The record as JSON text, as written beside the publish."""
        data = asdict(self)
        data["published"] = self.published.isoformat()
        return json.dumps(data, indent=2) + "\n"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PublishRecord:
        built_from = get(data, "built_from", dict, default=None)
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
            built_from=_dependency(built_from) if built_from else None,
            checks=get(data, "checks", dict, default={}),
            schema=get(data, "schema", int, default=SCHEMA),
        )


def new_record(
    plan: PublishPlan,
    source: Path,
    blender: str,
    object_names: list[str],
    dependencies: list[Dependency] | None = None,
    built_from: Dependency | None = None,
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
        built_from=built_from,
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


def built_from(entity: Entity, task: str) -> Dependency | None:
    """The publish a task starts from (its config's builds_on), if it has one."""
    upstream = entity.project.config.tasks[task].builds_on
    if upstream is None or not entity.has_task(upstream):
        return None
    record = hero_record(entity, upstream)
    if record is None:
        raise PipelineError(
            f"{entity.label} has no {upstream} publish yet, and {task} starts from it. "
            f"Publish the {upstream} first."
        )
    return Dependency(relative(entity.project, entity.hero_path(upstream)), record.version)


def relative(project: Project, path: Path) -> str:
    """A path inside the project, relative to its root, with forward slashes."""
    return Path(path).resolve().relative_to(project.root).as_posix()


def tool_version() -> str:
    """The add-on's version, from its manifest."""
    with _MANIFEST.open("rb") as handle:
        return tomllib.load(handle)["version"]


def _dependency(data: Any) -> Dependency:
    return Dependency(get(data, "path", str), get(data, "version", int, default=None))
