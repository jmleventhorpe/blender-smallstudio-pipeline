"""Reviewing a publish before it happens: what it would write, and what its checks say.

Check (the Publish panel's button) calls review(): it works out what Publish would write
from the open file, the same way Publish does, and runs the checks without writing
anything. What it would write is kept as a Preview (current), which the panel draws, so
drawing never reads the disk; Publish and opening another file clear it.

For an asset: which asset and task, the version it becomes, the hero it replaces, how many
objects, where a rig's materials come from, and whether it's published from inside
another asset's file. For a layout: the version, and each shot's frames, cut, cast and
what changed since the last publish (shots/core/layout.changes_since), with the shots
it would omit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import bpy

from ...interface.panels import DASH
from ...loading.blender import instances
from ...project.blender.identity import asset_identity, built_from
from ...project.core.project import Project
from ...shots.blender import layout
from ...shots.core.layout import changes_since
from ...workfiles.core.context import FileContext
from ..core.publishing import plan_publish, publish_target
from . import in_context, results
from . import layout as layout_publish
from .assets import pick_root
from .validation import subject_for, validator_for


@dataclass(frozen=True)
class ShotRow:
    shot: str  # The shot's own number, e.g. "0015".
    frames: str  # First to last frame of the shot's scene.
    cut: str  # Where it sits in the cut, first to last frame.
    cast: int
    change: str  # e.g. "retimed", or "" for none.


@dataclass
class Preview:
    title: str  # e.g. "hero · rig" or "010_010 · layout".
    writes: str  # The version it becomes, e.g. "hero_rig v005".
    facts: list[str] = field(default_factory=list)  # e.g. "Replaces hero_rig.blend (v004)".
    shots: list[ShotRow] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)


current: Preview | None = None


def clear() -> None:
    """Forget the last review: it was for another file, or something's been published."""
    global current
    current = None


def review(context: bpy.types.Context, project: Project, file: FileContext) -> results.LastPublish:
    """Work out what Publish would write and run its checks, keeping both for the panel."""
    global current
    if file.entity_kind == "sequence" and file.task == layout.LAYOUT:
        current, subjects = _layout(project, file)
    else:
        current, subjects = _asset(context, project, file)
    validator = validator_for(project)
    root = subjects[0][1].root if len(subjects) == 1 else None
    if root is not None and current.title.endswith("(in context)"):
        with in_context.in_asset_space(root, context.view_layer):  # Checked as it would be.
            checked = [results.Checked(label, validator.run(s), s) for label, s in subjects]
    else:
        checked = [results.Checked(label, validator.run(s), s) for label, s in subjects]
    last = results.LastPublish(checked, validator, checked_only=True)
    results.store(last)
    return last


def _asset(context: bpy.types.Context, project: Project, file: FileContext) -> tuple[Preview, list]:
    root = pick_root(context)
    identity = asset_identity(root)
    assert identity is not None  # pick_root only returns asset roots.
    target = publish_target(project, file, identity[0])
    asset, task = target.asset, target.task
    plan = plan_publish(asset, task)
    title = f"{asset.name} · {task}" + (" (in context)" if target.in_context else "")
    preview = Preview(title, plan.label)
    latest = asset.latest_publish_version(task)
    padding = project.config.version_padding
    if latest is None:
        preview.facts.append(f"First {task} publish of {asset.name}")
    else:
        preview.facts.append(f"Replaces {plan.hero.name} (v{latest:0{padding}d})")
    count = len(root.all_objects)
    preview.facts.append(f"Root {root.name}: {count} object{'s' if count != 1 else ''}")
    source = built_from(root)
    if source is not None and project.config.tasks[task].builds_on:
        version = f" v{source.version:0{padding}d}" if source.version else ""
        preview.facts.append(f"Materials from {Path(source.path).stem}{version}")
    if target.in_context:
        preview.facts.append(f"From {file.entity}'s file: saved as {asset.name}'s next workfile")
        preview.facts.append("and linked back here afterwards")
    return preview, [("", subject_for(root, target, file.entity))]


def _layout(project: Project, file: FileContext) -> tuple[Preview, list]:
    sequence = project.sequence(file.entity)
    master = layout.master_scene()
    for scene in bpy.data.scenes:  # As saving before a publish would, so IDs are checked.
        if layout.SHOT in scene:
            instances.number_instances(scene)
    cuts = layout.cut(master, layout_publish.casting_by_shot(master))
    changes, omitted = changes_since(sequence, cuts)
    plan = plan_publish(sequence, layout.LAYOUT)
    preview = Preview(f"{sequence.name} · {layout.LAYOUT}", plan.label)
    preview.facts.append(f"{len(cuts)} shot{'s' if len(cuts) != 1 else ''} in the cut")
    for cut in cuts:
        preview.shots.append(
            ShotRow(
                layout.shot_number(cut.shot),
                f"{cut.frame_start}{DASH}{cut.frame_end}",
                f"{cut.cut_in}{DASH}{cut.cut_out}",
                len(cut.casting),
                changes.get(cut.shot, ""),
            )
        )
    preview.omitted = [layout.shot_number(code) for code in omitted]
    return preview, layout_publish.shot_subjects(master, project)
