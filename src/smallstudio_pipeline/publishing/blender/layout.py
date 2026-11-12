"""Publishing a sequence's layout: the whole workfile, and the cut into each shot.

A layout publish is a Save Copy of the layout workfile, every scene included, since
bpy.data.libraries.write can't write scenes (spike T13): the versioned file, and the
hero through a temp file and a rename. The cut goes into each shot's metadata
(shots/core/layout.py). Checks run once per shot, on its scene, with the facts the shot
checks need in each subject's extras (see publishing/checks/blender/pipeline.py).
Animation publishes (animation.py) share the per-shot subjects and dependencies.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from publish_validator import Subject

from ...common.files import replace_with_retry
from ...loading.blender import instances
from ...loading.blender.libraries import linked_publishes
from ...loading.core.updates import publish_version
from ...project.core.metadata import CastEntry
from ...project.core.project import Project
from ...shots.blender import layout
from ..core.publishing import Dependency, PublishPlan


def shot_subjects(
    master: bpy.types.Scene, project: Project, task: str = layout.LAYOUT
) -> list[tuple[str, Subject]]:
    """What the checks validate: each shot in the cut, by its code. For animation, each
    also carries the cast layout last published, to check against."""
    known = {asset.name for asset in project.assets()}
    subjects = []
    for strip in layout.shot_strips(master):
        scene, code = strip.scene, layout.strip_shot(strip)
        assert scene is not None  # shot_strips only returns strips showing a shot.
        found = instances.instances(scene)
        extras = {
            "entity_kind": "shot",
            "shot": code,
            "scene": scene,
            "instances": [(instance.holder, instance.asset) for instance in found],
            "known_assets": known,
        }
        if task != layout.LAYOUT:
            cast = project.shot(code).metadata.casting
            extras["layout_cast"] = [(entry.asset, entry.instance_id) for entry in cast]
        subject = Subject(
            name=code, asset_type=None, task=task, root=scene.collection, extras=extras
        )
        subjects.append((code, subject))
    return subjects


def casting_by_shot(master: bpy.types.Scene) -> dict[str, tuple[CastEntry, ...]]:
    """Each shot's casting, by its code."""
    found = {}
    for strip in layout.shot_strips(master):
        assert strip.scene is not None  # shot_strips only returns strips showing a shot.
        found[layout.strip_shot(strip)] = instances.casting(strip.scene)
    return found


def write_layout(plan: PublishPlan) -> None:
    """Write the versioned file and the hero as copies of the open workfile."""
    plan.hero.parent.mkdir(parents=True, exist_ok=True)
    save_copy(plan.path)
    # The temp file sits beside the hero so relative paths and the rename both hold.
    temp = plan.hero.with_name(f"{plan.hero.stem}.tmp.blend")
    save_copy(temp)
    replace_with_retry(temp, plan.hero)


def save_copy(path: Path) -> None:
    """Save a copy of the open file at path; the session stays on its own file."""
    bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True, relative_remap=True)


def dependencies(project: Project) -> list[Dependency]:
    """The publishes the layout file links (sets, characters, props), with their versions."""
    return [Dependency(path, publish_version(project, path)) for path in linked_publishes(project)]
