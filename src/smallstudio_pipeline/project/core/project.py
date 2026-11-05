"""A project: its folder, settings, path templates and tracker, and the entities in it.

Project.find() works out the project from any path inside it (the nearest folder with a
pipeline.toml); Project.create() starts a new one. From a Project you look up and create
assets, sequences and shots, and turn a template and its fields into an absolute path
(path(), find_files()), with renders going under the render root.

    project = Project.find(Path("/mnt/show/assets/character/hero"))
    hero = project.asset("hero")
"""

from __future__ import annotations

import difflib
from pathlib import Path

from ...common.errors import EntityExists, EntityNotFound, PipelineError
from .config import PROJECT_FILE, AssetType, Config, load_config
from .entities import Asset, Sequence, Shot
from .metadata import AssetMetadata, SequenceMetadata
from .naming import EPISODE_DIGITS, SEQUENCE_DIGITS, SequenceCode, check_name, next_number
from .templates import Fields, Template, build_templates
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
        return self._root_for(found) / found.format(**fields)

    def find_files(self, template: str, **known: str | int) -> list[tuple[Path, Fields]]:
        """Return the existing files that fit a template, with their fields."""
        found = self.templates[template]
        return found.find(self._root_for(found), **known)

    def _root_for(self, template: Template) -> Path:
        return self.render_root if template.render else self.root

    # Assets

    def assets(self, asset_type: str | None = None) -> list[Asset]:
        """The project's assets by name, only of one type if given."""
        assets = [Asset(self, metadata) for metadata in self.tracker.assets()]
        return sorted(
            (asset for asset in assets if asset_type in (None, asset.asset_type)),
            key=lambda asset: asset.name,
        )

    def asset(self, name: str) -> Asset:
        """The asset with this name, or raise EntityNotFound."""
        return _pick({asset.name: asset for asset in self.assets()}, name, "asset")

    def asset_type(self, name: str) -> AssetType:
        """Return an asset type's settings, or raise if the project has no such type."""
        if name not in self.config.asset_types:
            known = ", ".join(self.config.asset_types)
            raise PipelineError(f"'{name}' isn't an asset type. Asset types are: {known}.")
        return self.config.asset_types[name]

    def create_asset(self, asset_type: str, name: str, tasks: list[str] | None = None) -> Asset:
        """Create an asset with its type's required tasks, plus any optional ones in `tasks`."""
        check_name(name, self.config.name_pattern)
        task_list = self.asset_type(asset_type).task_list(tasks or ())
        if any(asset.name == name for asset in self.assets()):
            raise EntityExists(
                f"There's already an asset called '{name}'. Asset names are unique in a project."
            )
        metadata = AssetMetadata(name, asset_type, task_list)
        self.tracker.save_asset(metadata)
        return Asset(self, metadata)

    # Any entity

    def categories(self) -> list[str]:
        """What the dialogs browse by: each asset type, then "sequence" and "shot"."""
        return [*self.config.asset_types, "sequence", "shot"]

    def entities_in(self, category: str) -> list[Asset] | list[Sequence] | list[Shot]:
        """Every entity in a category: an asset type, "sequence" or "shot"."""
        if category == "sequence":
            return self.sequences()
        if category == "shot":
            return self.shots()
        return self.assets(self.asset_type(category).name)

    def entity(self, entity_kind: str, name: str) -> Asset | Sequence | Shot:
        """Look up an entity by its kind ("asset", "sequence", "shot") and name or code."""
        if entity_kind == "sequence":
            return self.sequence(name)
        if entity_kind == "shot":
            return self.shot(name)
        return self.asset(name)

    # Sequences and shots

    def episodes(self) -> list[str]:
        """The episodes that have sequences."""
        return sorted({seq.code.episode for seq in self.sequences() if seq.code.episode})

    def next_episode(self) -> str:
        """The code a new episode gets: a step past the highest."""
        number = next_number([int(code) for code in self.episodes()], self.config.code_step)
        return f"{number:0{EPISODE_DIGITS}d}"

    def sequences(self, episode: str | None = None) -> list[Sequence]:
        """The sequences in order, only in one episode if given."""
        sequences = [Sequence(self, metadata) for metadata in self.tracker.sequences()]
        return sorted(
            (seq for seq in sequences if episode in (None, seq.code.episode)),
            key=lambda seq: seq.code,
        )

    def sequence(self, code: str) -> Sequence:
        """The sequence with this code, or raise EntityNotFound."""
        return _pick({str(seq.code): seq for seq in self.sequences()}, code, "sequence")

    def create_sequence(self, episode: str | None = None, title: str = "") -> Sequence:
        """Create the next sequence in an episode, numbered a step past the last.

        A sequence's code only names it: the order sequences play in belongs to the
        episode's edit, so reordering them never renumbers anything.
        """
        if self.config.episodes and episode is None:
            raise PipelineError("This project uses episodes: choose the sequence's episode.")
        if not self.config.episodes and episode is not None:
            raise PipelineError("This project doesn't use episodes.")
        existing = [int(seq.code.number) for seq in self.sequences(episode)]
        number = next_number(existing, self.config.code_step)
        code = SequenceCode(episode, f"{number:0{SEQUENCE_DIGITS}d}")
        metadata = SequenceMetadata(str(code), title.strip())
        self.tracker.save_sequence(metadata)
        return Sequence(self, metadata)

    def shots(self, include_omitted: bool = False) -> list[Shot]:
        """The shots in order, with omitted ones only if asked."""
        shots = [Shot(self, metadata) for metadata in self.tracker.shots()]
        return sorted(
            (shot for shot in shots if include_omitted or not shot.omitted),
            key=lambda shot: shot.code,
        )

    def shot(self, code: str) -> Shot:
        """The shot with this code, omitted or not, or raise EntityNotFound."""
        shots = self.shots(include_omitted=True)
        return _pick({str(shot.code): shot for shot in shots}, code, "shot")


def _pick[E](candidates: dict[str, E], wanted: str, what: str) -> E:
    """Return the entity called `wanted`, or raise EntityNotFound with a suggestion."""
    if wanted in candidates:
        return candidates[wanted]
    matches = difflib.get_close_matches(wanted, list(candidates), n=1)
    suggestion = f" Did you mean '{matches[0]}'?" if matches else ""
    raise EntityNotFound(f"There's no {what} '{wanted}'.{suggestion}")
