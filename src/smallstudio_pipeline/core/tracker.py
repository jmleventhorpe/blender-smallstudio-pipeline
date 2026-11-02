"""Where entity data lives: the filesystem now, with room for a Kitsu tracker later."""

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
            # A copied folder can carry another asset's file; trust neither silently.
            if (metadata.name, metadata.asset_type) != (fields["asset"], fields["asset_type"]):
                raise MetadataError(
                    f"{path} describes {metadata.asset_type} '{metadata.name}', "
                    f"but sits in the folder for {fields['asset_type']} '{fields['asset']}'."
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
            _check_code(path, "sequence", metadata.code, fields["sequence"])
            sequences.append(metadata)
        return sequences

    def save_sequence(self, metadata: SequenceMetadata) -> None:
        write_metadata(self.root / self._sequence_file.format(sequence=metadata.code), metadata)

    def shots(self) -> list[ShotMetadata]:
        shots = []
        for path, fields in self._shot_file.find(self.root):
            metadata = read_metadata(path, ShotMetadata)
            _check_code(path, "shot", metadata.code, fields["shot"])
            shots.append(metadata)
        return shots

    def save_shot(self, metadata: ShotMetadata) -> None:
        write_metadata(self.root / self._shot_file.format(shot=metadata.code), metadata)


def _check_code(path: Path, kind: str, code: str, folder_code: str | int) -> None:
    if code != folder_code:
        raise MetadataError(
            f"{path} describes {kind} {code}, but sits in the folder for {folder_code}."
        )
