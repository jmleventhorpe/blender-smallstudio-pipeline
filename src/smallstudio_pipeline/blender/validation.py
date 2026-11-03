"""Checking an asset with publish-validator before it's published.

validator_for() sets up the validator with the pipeline's checks (checks/) and settings
(validation.toml), then the project's own if it has them. subject_for() describes the
asset to the checks; the facts they need (identity, target, the last publish's object
names) go in its extras, because check files can't import the add-on.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from publish_validator import Config, Report, Subject, Validator
from publish_validator.hosts.blender import BlenderHost

from ..core.project import Project
from ..core.publishing import PublishTarget, hero_record
from .identity import asset_identity

ADDON = Path(__file__).resolve().parent.parent
PIPELINE_CHECKS = ADDON / "checks"
PIPELINE_SETTINGS = ADDON / "validation.toml"
PROJECT_SETTINGS = "validation.toml"  # A project's own settings, beside pipeline.toml.
PROJECT_CHECKS = "checks"  # A project's own checks folder.


def validator_for(project: Project) -> Validator:
    """The validator with the pipeline's checks and settings, then the project's."""
    config = Config()
    config.read(PIPELINE_SETTINGS)
    if (project.root / PROJECT_SETTINGS).is_file():
        config.read(project.root / PROJECT_SETTINGS)
    folders = [PIPELINE_CHECKS]
    if (project.root / PROJECT_CHECKS).is_dir():
        folders.append(project.root / PROJECT_CHECKS)
    return Validator(BlenderHost(), config=config, check_paths=folders)


def subject_for(root: bpy.types.Collection, target: PublishTarget, file_entity: str) -> Subject:
    """What the checks validate, with the pipeline facts they need in extras."""
    asset = target.asset
    record = hero_record(asset, target.task)
    previous = None
    if record is not None:
        padding = asset.project.config.version_padding
        previous = {
            "version": record.version,
            "label": f"v{record.version:0{padding}d}",
            "object_names": record.object_names,
        }
    return Subject(
        name=asset.name,
        asset_type=asset.asset_type,
        task=target.task,
        root=root,
        extras={
            "asset": asset.name,
            "asset_type": asset.asset_type,
            "identity": asset_identity(root),
            "in_context": target.in_context,
            "file_entity": file_entity,
            "previous": previous,
        },
    )


def validate(
    root: bpy.types.Collection, target: PublishTarget, file_entity: str, fix: bool = False
) -> Report:
    """Run every check that applies. The report also lists any check that failed to load."""
    validator = validator_for(target.asset.project)
    return validator.run(subject_for(root, target, file_entity), fix=fix)
