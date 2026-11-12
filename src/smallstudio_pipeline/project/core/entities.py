"""Assets, sequences and shots: their tasks, and where each task's files go.

Entity holds what the three share: each task's workfiles, publishes, hero file and
renders, and their version numbers, all from the templates and the files on disk, with
clear errors for tasks the entity doesn't have or that don't publish or render there.
Asset adds its type's settings and optional tasks; Sequence creates shots; Shot
carries its frame range and can be omitted.

    hero = project.asset("hero")
    hero.workfile_path("rig", hero.next_workfile_version("rig"))
    hero.hero_path("rig")                   # The file shots link.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from ...common.errors import PipelineError
from .config import AssetType, Task
from .metadata import AssetMetadata, SequenceMetadata, ShotMetadata
from .naming import SHOT_DIGITS, SequenceCode, ShotCode, next_number

if TYPE_CHECKING:  # Only for type hints: project.py imports this module.
    from .project import Project


class Entity:
    """What assets, sequences and shots share: workfiles, publishes and renders per task."""

    kind: ClassVar[str]  # "asset", "sequence" or "shot": picks the templates.
    name: str  # The asset's name, or the sequence or shot code.

    def __init__(self, project: Project):
        self.project = project

    @property
    def fields(self) -> dict[str, str]:
        """The template fields that identify this entity."""
        raise NotImplementedError

    @property
    def label(self) -> str:
        """How the entity is named in messages."""
        raise NotImplementedError

    @property
    def tasks(self) -> list[str]:
        """The tasks this entity has workfiles for."""
        tasks = self.project.config.tasks.values()
        return [task.name for task in tasks if task.entity == self.kind]

    def has_task(self, task: str) -> bool:
        """Whether the entity has this task."""
        return task in self.tasks

    def tasks_with_workfiles(self) -> list[str]:
        """The tasks with at least one workfile."""
        return [task for task in self.tasks if self.workfile_versions(task)]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and (self.kind, self.fields) == (other.kind, other.fields)

    def __hash__(self) -> int:
        return hash((self.kind, tuple(self.fields.items())))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.label!r})"

    # Workfiles

    def workfile_path(self, task: str, version: int) -> Path:
        """Where a task's workfile of this version goes."""
        self._task(task)
        return self.project.path(f"{self.kind}_work", **self.fields, task=task, version=version)

    def workfile_versions(self, task: str) -> list[int]:
        """The task's existing workfile versions, lowest first."""
        self._task(task)
        return self._versions(f"{self.kind}_work", task)

    def next_workfile_version(self, task: str) -> int:
        """The version after the task's highest workfile."""
        return max(self.workfile_versions(task), default=0) + 1

    # Publishes

    def publish_path(self, task: str, version: int) -> Path:
        """Where a task's publish of this version goes."""
        self._publishing_task(task)
        return self.project.path(f"{self.kind}_publish", **self.fields, task=task, version=version)

    def hero_path(self, task: str) -> Path:
        """The unversioned publish that other files link, always the latest."""
        self._publishing_task(task)
        return self.project.path(f"{self.kind}_hero", **self.fields, task=task)

    def publish_versions(self, task: str) -> list[int]:
        """The task's existing publish versions, lowest first."""
        self._publishing_task(task)
        return self._versions(f"{self.kind}_publish", task)

    def latest_publish_version(self, task: str) -> int | None:
        """The task's highest publish version, or None if it has none."""
        return max(self.publish_versions(task), default=None)

    def next_publish_version(self, task: str) -> int:
        """The version the task's next publish gets."""
        return max(self.publish_versions(task), default=0) + 1

    # Renders

    def render_path(self, task: str, version: int) -> Path:
        """Where a task's render of this version goes."""
        found = self.project.config.tasks.get(task)
        if found is None or found.renders != self.kind:
            raise PipelineError(f"{task} doesn't render per {self.kind}.")
        return self.project.path(f"{self.kind}_render", **self.fields, task=task, version=version)

    def _task(self, task: str) -> Task:
        if not self.has_task(task):
            raise PipelineError(f"{self.label} has no {task} task.")
        return self.project.config.tasks[task]

    def _publishing_task(self, task: str) -> Task:
        found = self._task(task)
        if not found.publishes:
            raise PipelineError(f"{task} doesn't publish.")
        return found

    def _versions(self, template: str, task: str) -> list[int]:
        found = self.project.find_files(template, **self.fields, task=task)
        return sorted(int(fields["version"]) for _, fields in found)


class Asset(Entity):
    kind = "asset"

    def __init__(self, project: Project, metadata: AssetMetadata):
        super().__init__(project)
        self.metadata = metadata

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def asset_type(self) -> str:
        return self.metadata.asset_type

    @property
    def settings(self) -> AssetType:
        """The settings for this asset's type."""
        return self.project.asset_type(self.asset_type)

    @property
    def tasks(self) -> list[str]:
        return list(self.metadata.tasks)

    @property
    def fields(self) -> dict[str, str]:
        return {"asset_type": self.asset_type, "asset": self.name}

    @property
    def label(self) -> str:
        return self.name

    def add_task(self, task: str) -> None:
        """Add one of the type's optional tasks, e.g. the rig task for a prop."""
        if self.has_task(task):
            raise PipelineError(f"{self.name} already has a {task} task.")
        self.metadata.tasks = self.settings.task_list([*self.tasks, task])
        self.save()

    def save(self) -> None:
        """Write the asset's metadata."""
        self.project.tracker.save_asset(self.metadata)


class Sequence(Entity):
    kind = "sequence"

    def __init__(self, project: Project, metadata: SequenceMetadata):
        super().__init__(project)
        self.metadata = metadata
        self.code = SequenceCode.parse(metadata.code, project.config.episodes)

    @property
    def name(self) -> str:
        return str(self.code)

    @property
    def fields(self) -> dict[str, str]:
        return {"sequence": self.name}

    @property
    def label(self) -> str:
        return f"sequence {self.code}"

    @property
    def title(self) -> str:
        """What happens in it, e.g. "Opening chase", or "" if it has no title."""
        return self.metadata.title

    def shots(self, include_omitted: bool = False) -> list[Shot]:
        """The sequence's shots, in order."""
        shots = self.project.shots(include_omitted)
        return [shot for shot in shots if shot.code.sequence == self.code]

    def create_shot(self, after: Shot | None = None, first: bool = False) -> Shot:
        """Create the next shot, one between `after` and the next, or one before the first.

        Omitted shots keep their numbers, so a new shot never reuses one.
        """
        if after is not None and after.code.sequence != self.code:
            raise PipelineError(f"Shot {after.code} isn't in {self.label}.")
        existing = [int(shot.code.number) for shot in self.shots(include_omitted=True)]
        step = self.project.config.code_step
        position = 0 if first else int(after.code.number) if after else None
        number = next_number(existing, step, position)
        metadata = ShotMetadata(str(ShotCode(self.code, f"{number:0{SHOT_DIGITS}d}")))
        self.project.tracker.save_shot(metadata)
        return Shot(self.project, metadata)


class Shot(Entity):
    kind = "shot"

    def __init__(self, project: Project, metadata: ShotMetadata):
        super().__init__(project)
        self.metadata = metadata
        self.code = ShotCode.parse(metadata.code, project.config.episodes)

    @property
    def name(self) -> str:
        return str(self.code)

    @property
    def fields(self) -> dict[str, str]:
        return {"shot": self.name}

    @property
    def label(self) -> str:
        return f"shot {self.code}"

    @property
    def sequence(self) -> Sequence:
        """The sequence the shot belongs to."""
        return self.project.sequence(str(self.code.sequence))

    @property
    def frame_range(self) -> tuple[int, int] | None:
        """(first, last) frame, or None until layout sets it."""
        start, end = self.metadata.frame_start, self.metadata.frame_end
        return None if start is None or end is None else (start, end)

    @property
    def omitted(self) -> bool:
        return self.metadata.omitted

    def omit(self) -> None:
        """Mark the shot omitted. Nothing is deleted; its files and number stay."""
        self.metadata.omitted = True
        self.save()

    def save(self) -> None:
        """Write the shot's metadata."""
        self.project.tracker.save_shot(self.metadata)
