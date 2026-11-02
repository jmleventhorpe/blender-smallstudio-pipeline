"""The project and its assets, sequences and shots: what exists, and where its files go.

project = Project.find(Path("/mnt/show/assets/character/hero"))
hero = project.asset("hero")
hero.workfile_path("rigging", hero.next_workfile_version("rigging"))
hero.hero_path(hero.shot_task())        # The file shots link.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import ClassVar

from .config import PROJECT_FILE, AssetType, Config, Task, load_config
from .errors import EntityExists, EntityNotFound, PipelineError
from .metadata import AssetMetadata, SequenceMetadata, ShotMetadata
from .naming import SEQUENCE_DIGITS, SHOT_DIGITS, SequenceCode, ShotCode, check_name, next_number
from .templates import Fields, build_templates
from .tracker import FilesystemTracker, Tracker

NEW_PROJECT_CONFIG = """\
# Pipeline settings for this project. Anything set here overrides the add-on's
# defaults.toml; tables merge key by key.
"""


class Project:
    """A project folder: its config, path templates and entities."""

    def __init__(self, root: Path, config: Config | None = None, tracker: Tracker | None = None):
        self.root = Path(root).resolve()
        self.config = config or load_config(self.root)
        self.templates = build_templates(self.config)
        # Joining an absolute render_root replaces the root; a relative one sits under it.
        self.render_root = (self.root / self.config.render_root).resolve()
        self.tracker = tracker or FilesystemTracker(self.root, self.templates)

    def __repr__(self) -> str:
        return f"Project({str(self.root)!r})"

    @classmethod
    def create(cls, root: Path) -> Project:
        """Make a new project folder with a starter pipeline.toml."""
        root = Path(root)
        if (root / PROJECT_FILE).exists():
            raise EntityExists(f"{root} is already a project.")
        root.mkdir(parents=True, exist_ok=True)
        (root / PROJECT_FILE).write_text(NEW_PROJECT_CONFIG)
        return cls(root)

    @classmethod
    def find(cls, path: Path) -> Project | None:
        """Return the project a path belongs to: the nearest folder with a pipeline.toml."""
        path = Path(path).resolve()
        for folder in (path, *path.parents):
            if (folder / PROJECT_FILE).is_file():
                return cls(folder)
        return None

    def path(self, template: str, **fields: str | int) -> Path:
        """Return the absolute path a template gives for these fields."""
        found = self.templates[template]
        return (self.render_root if found.render else self.root) / found.format(**fields)

    def find_files(self, template: str, **known: str | int) -> list[tuple[Path, Fields]]:
        """Return the existing files that fit a template, with their fields."""
        found = self.templates[template]
        return found.find(self.render_root if found.render else self.root, **known)

    # Assets

    def assets(self, asset_type: str | None = None) -> list[Asset]:
        assets = [Asset(self, metadata) for metadata in self.tracker.assets()]
        return sorted(
            (asset for asset in assets if asset_type in (None, asset.asset_type)),
            key=lambda asset: asset.name,
        )

    def asset(self, name: str) -> Asset:
        assets = self.assets()
        for asset in assets:
            if asset.name == name:
                return asset
        names = [asset.name for asset in assets]
        raise EntityNotFound(f"There's no asset called '{name}'.{_did_you_mean(name, names)}")

    def create_asset(self, asset_type: str, name: str, tasks: list[str] | None = None) -> Asset:
        """Create an asset with its type's required tasks, plus any optional ones in `tasks`."""
        check_name(name, self.config.name_pattern)
        kind = self.asset_type_settings(asset_type)
        if any(asset.name == name for asset in self.assets()):
            raise EntityExists(
                f"There's already an asset called '{name}'. Asset names are unique in a project."
            )
        chosen = set(kind.required_tasks) | set(tasks or ())
        unknown = sorted(chosen - set(kind.tasks))
        if unknown:
            raise PipelineError(f"{asset_type} assets don't have a {unknown[0]} task.")
        metadata = AssetMetadata(name, asset_type, [task for task in kind.tasks if task in chosen])
        self.tracker.save_asset(metadata)
        return Asset(self, metadata)

    def asset_type_settings(self, name: str) -> AssetType:
        """Return the config for an asset type, or raise if the project has no such type."""
        if name not in self.config.asset_types:
            known = ", ".join(self.config.asset_types)
            raise PipelineError(f"'{name}' isn't an asset type. Asset types are: {known}.")
        return self.config.asset_types[name]

    # Sequences and shots

    def episodes(self) -> list[str]:
        return sorted({seq.code.episode for seq in self.sequences() if seq.code.episode})

    def sequences(self, episode: str | None = None) -> list[Sequence]:
        sequences = [Sequence(self, metadata) for metadata in self.tracker.sequences()]
        return sorted(
            (seq for seq in sequences if episode in (None, seq.code.episode)),
            key=lambda seq: seq.code,
        )

    def sequence(self, code: str) -> Sequence:
        sequences = self.sequences()
        for sequence in sequences:
            if str(sequence.code) == code:
                return sequence
        codes = [str(sequence.code) for sequence in sequences]
        raise EntityNotFound(f"There's no sequence {code}.{_did_you_mean(code, codes)}")

    def create_sequence(
        self, episode: str | None = None, after: Sequence | None = None
    ) -> Sequence:
        """Create the next sequence in an episode, or one between `after` and the next."""
        if self.config.episodes and episode is None:
            raise PipelineError("This project uses episodes: choose the sequence's episode.")
        if not self.config.episodes and episode is not None:
            raise PipelineError("This project doesn't use episodes.")
        if after is not None and after.code.episode != episode:
            raise PipelineError(f"Sequence {after.code} isn't in episode {episode}.")
        existing = [int(seq.code.sequence) for seq in self.sequences(episode)]
        number = next_number(
            existing, self.config.code_step, int(after.code.sequence) if after else None
        )
        code = SequenceCode(episode, f"{number:0{SEQUENCE_DIGITS}d}")
        metadata = SequenceMetadata(str(code))
        self.tracker.save_sequence(metadata)
        return Sequence(self, metadata)

    def shots(self, include_omitted: bool = False) -> list[Shot]:
        shots = [Shot(self, metadata) for metadata in self.tracker.shots()]
        return sorted(
            (shot for shot in shots if include_omitted or not shot.omitted),
            key=lambda shot: shot.code,
        )

    def shot(self, code: str) -> Shot:
        shots = self.shots(include_omitted=True)
        for shot in shots:
            if str(shot.code) == code:
                return shot
        codes = [str(shot.code) for shot in shots]
        raise EntityNotFound(f"There's no shot {code}.{_did_you_mean(code, codes)}")


class Entity:
    """What assets, sequences and shots share: workfiles, publishes and renders per task."""

    kind: ClassVar[str]  # "asset", "sequence" or "shot": picks the templates.

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

    def has_task(self, task: str) -> bool:
        found = self.project.config.tasks.get(task)
        return found is not None and found.entity == self.kind

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and (self.kind, self.fields) == (other.kind, other.fields)

    def __hash__(self) -> int:
        return hash((self.kind, tuple(self.fields.items())))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.label!r})"

    # Workfiles

    def workfile_path(self, task: str, version: int) -> Path:
        self._task(task)
        return self.project.path(f"{self.kind}_work", **self.fields, task=task, version=version)

    def workfile_versions(self, task: str) -> list[int]:
        self._task(task)
        return self._versions(f"{self.kind}_work", task)

    def next_workfile_version(self, task: str) -> int:
        return max(self.workfile_versions(task), default=0) + 1

    # Publishes

    def publish_path(self, task: str, version: int) -> Path:
        self._publishing_task(task)
        return self.project.path(f"{self.kind}_publish", **self.fields, task=task, version=version)

    def hero_path(self, task: str) -> Path:
        """The unversioned publish that other files link, always the latest."""
        self._publishing_task(task)
        return self.project.path(f"{self.kind}_hero", **self.fields, task=task)

    def publish_versions(self, task: str) -> list[int]:
        self._publishing_task(task)
        return self._versions(f"{self.kind}_publish", task)

    def latest_publish_version(self, task: str) -> int | None:
        return max(self.publish_versions(task), default=None)

    def next_publish_version(self, task: str) -> int:
        return (self.latest_publish_version(task) or 0) + 1

    # Renders

    def render_path(self, task: str, version: int) -> Path:
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
    def tasks(self) -> list[str]:
        return list(self.metadata.tasks)

    @property
    def fields(self) -> dict[str, str]:
        return {"asset_type": self.asset_type, "asset": self.name}

    @property
    def label(self) -> str:
        return self.name

    def has_task(self, task: str) -> bool:
        return task in self.metadata.tasks

    def shot_task(self) -> str:
        """The task whose publish shots link: the first in the type's shot_link it has."""
        asset_type = self.project.asset_type_settings(self.asset_type)
        return next(task for task in asset_type.shot_link if self.has_task(task))

    def add_task(self, task: str) -> None:
        """Add one of the type's optional tasks, e.g. rigging for a prop."""
        asset_type = self.project.asset_type_settings(self.asset_type)
        if self.has_task(task):
            raise PipelineError(f"{self.name} already has a {task} task.")
        if task not in asset_type.tasks:
            raise PipelineError(f"{self.asset_type} assets don't have a {task} task.")
        chosen = {*self.metadata.tasks, task}
        self.metadata.tasks = [name for name in asset_type.tasks if name in chosen]
        self.save()

    def save(self) -> None:
        self.project.tracker.save_asset(self.metadata)


class Sequence(Entity):
    kind = "sequence"

    def __init__(self, project: Project, metadata: SequenceMetadata):
        super().__init__(project)
        self.metadata = metadata
        self.code = SequenceCode.parse(metadata.code, project.config.episodes)

    @property
    def fields(self) -> dict[str, str]:
        return {"sequence": str(self.code)}

    @property
    def label(self) -> str:
        return f"sequence {self.code}"

    def shots(self, include_omitted: bool = False) -> list[Shot]:
        return [
            shot
            for shot in self.project.shots(include_omitted)
            if shot.code.sequence_code == self.code
        ]

    def create_shot(self, after: Shot | None = None) -> Shot:
        """Create the next shot, or one between `after` and the next. Omitted shots keep
        their numbers, so a new shot never reuses one."""
        if after is not None and after.code.sequence_code != self.code:
            raise PipelineError(f"Shot {after.code} isn't in {self.label}.")
        existing = [int(shot.code.shot) for shot in self.shots(include_omitted=True)]
        number = next_number(
            existing, self.project.config.code_step, int(after.code.shot) if after else None
        )
        code = ShotCode(self.code.episode, self.code.sequence, f"{number:0{SHOT_DIGITS}d}")
        metadata = ShotMetadata(str(code))
        self.project.tracker.save_shot(metadata)
        return Shot(self.project, metadata)


class Shot(Entity):
    kind = "shot"

    def __init__(self, project: Project, metadata: ShotMetadata):
        super().__init__(project)
        self.metadata = metadata
        self.code = ShotCode.parse(metadata.code, project.config.episodes)

    @property
    def fields(self) -> dict[str, str]:
        return {"shot": str(self.code)}

    @property
    def label(self) -> str:
        return f"shot {self.code}"

    @property
    def sequence(self) -> Sequence:
        return self.project.sequence(str(self.code.sequence_code))

    @property
    def frame_range(self) -> tuple[int, int] | None:
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
        self.project.tracker.save_shot(self.metadata)


def _did_you_mean(name: str, candidates: list[str]) -> str:
    matches = difflib.get_close_matches(name, candidates, n=1)
    return f" Did you mean '{matches[0]}'?" if matches else ""
