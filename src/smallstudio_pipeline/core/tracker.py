"""Where entity data comes from: the filesystem now, a production tracker (Kitsu) later.

The Tracker interface lists and saves assets, sequences and shots. FilesystemTracker
keeps them as JSON metadata files found through the templates, and refuses a file copied
into another entity's folder. Paths never come from a tracker, whichever one is used:
they always come from the templates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .errors import MetadataError
from .metadata import (
    AssetMetadata,
    SequenceMetadata,
    ShotMetadata,
    read_metadata,
    write_metadata,
)
from .templates import Template


class Tracker(Protocol):
    """The entity data the pipeline needs. Paths always come from templates, not the tracker."""

    def assets(self) -> list[AssetMetadata]: ...
    def save_asset(self, metadata: AssetMetadata) -> None: ...
    def sequences(self) -> list[SequenceMetadata]: ...
    def save_sequence(self, metadata: SequenceMetadata) -> None: ...
    def shots(self) -> list[ShotMetadata]: ...
    def save_shot(self, metadata: ShotMetadata) -> None: ...


class FilesystemTracker:
    """Entity data as a JSON file in each entity's folder, found through the templates."""

    def __init__(self, root: Path, templates: dict[str, Template]):
        self.root = root
        self._asset_file = templates["asset_metadata"]
        self._sequence_file = templates["sequence_metadata"]
        self._shot_file = templates["shot_metadata"]

    def assets(self) -> list[AssetMetadata]:
        assets = []
        for path, fields in self._asset_file.find(self.root):
            metadata = read_metadata(path, AssetMetadata)
            _check_folder(
                path,
                f"{metadata.asset_type} '{metadata.name}'",
                f"{fields['asset_type']} '{fields['asset']}'",
            )
            assets.append(metadata)
        return assets

    def save_asset(self, metadata: AssetMetadata) -> None:
        path = self._asset_file.format(asset_type=metadata.asset_type, asset=metadata.name)
        write_metadata(self.root / path, metadata)

    def sequences(self) -> list[SequenceMetadata]:
        sequences = []
        for path, fields in self._sequence_file.find(self.root):
            metadata = read_metadata(path, SequenceMetadata)
            _check_folder(path, f"sequence {metadata.code}", f"sequence {fields['sequence']}")
            sequences.append(metadata)
        return sequences

    def save_sequence(self, metadata: SequenceMetadata) -> None:
        write_metadata(self.root / self._sequence_file.format(sequence=metadata.code), metadata)

    def shots(self) -> list[ShotMetadata]:
        shots = []
        for path, fields in self._shot_file.find(self.root):
            metadata = read_metadata(path, ShotMetadata)
            _check_folder(path, f"shot {metadata.code}", f"shot {fields['shot']}")
            shots.append(metadata)
        return shots

    def save_shot(self, metadata: ShotMetadata) -> None:
        write_metadata(self.root / self._shot_file.format(shot=metadata.code), metadata)


def _check_folder(path: Path, in_file: str, in_folder: str) -> None:
    """A copied folder can carry another entity's file; don't trust either silently."""
    if in_file != in_folder:
        raise MetadataError(f"{path} describes {in_file}, but sits in the folder for {in_folder}.")
