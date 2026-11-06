"""What a layout publish records: each shot's frame range, cut points and casting.

A sequence's layout file holds the cut, with a strip per shot in its master scene.
Publishing layout reads each strip as a ShotCut, and apply_cut() writes them into the
shots' metadata, which later stages read: the frame range the shot's scene covers, where
the shot sits in the cut (for Assemble Edit to trim the layout playblast), and the
instances standing in it. Shots with no strip are marked omitted, and a strip for an
omitted shot brings it back. changes_since() says, before publishing, what that would
change in each shot.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...common.errors import PipelineError
from ...project.core.entities import Sequence
from ...project.core.metadata import CastEntry


@dataclass(frozen=True)
class ShotCut:
    shot: str  # The shot's code.
    frame_start: int  # The frames of the shot's scene its strip shows.
    frame_end: int
    cut_in: int  # Where the strip starts and ends in the cut.
    cut_out: int
    casting: tuple[CastEntry, ...] = ()


@dataclass
class CutChanges:
    updated: list[str] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)  # No strip any more.
    restored: list[str] = field(default_factory=list)  # Omitted before, back in the cut.

    @property
    def summary(self) -> str:
        """e.g. "4 shots; omitted 010_010_0030"."""
        parts = [f"{len(self.updated)} shots"]
        if self.omitted:
            parts.append(f"omitted {', '.join(self.omitted)}")
        if self.restored:
            parts.append(f"restored {', '.join(self.restored)}")
        return "; ".join(parts)


def changes_since(sequence: Sequence, cuts: list[ShotCut]) -> tuple[dict[str, str], list[str]]:
    """What publishing this cut would change in each shot, and which shots it would omit.

    Each shot in the cut gets "new" (never published), "restored" (omitted before),
    "retimed" (its length changed), "moved" (same length, elsewhere in the cut),
    "cast changed", several of those joined with ", ", or "" for no change.
    """
    shots = {str(shot.code): shot for shot in sequence.shots(include_omitted=True)}
    found = {}
    for cut in cuts:
        shot = shots.get(cut.shot)
        if shot is None:
            found[cut.shot] = "new"
            continue
        data, notes = shot.metadata, []
        if shot.omitted:
            notes.append("restored")
        elif data.frame_start is None or data.frame_end is None:
            notes.append("new")
        else:
            if data.frame_end - data.frame_start != cut.frame_end - cut.frame_start:
                notes.append("retimed")
            elif (data.cut_in, data.cut_out) != (cut.cut_in, cut.cut_out):
                notes.append("moved")
            if sorted(map(_cast_key, data.casting)) != sorted(map(_cast_key, cut.casting)):
                notes.append("cast changed")
        found[cut.shot] = ", ".join(notes)
    in_cut = {cut.shot for cut in cuts}
    omitted = sorted(
        code for code, shot in shots.items() if code not in in_cut and not shot.omitted
    )
    return found, omitted


def _cast_key(entry: CastEntry) -> tuple[str, str]:
    return entry.asset, entry.instance_id


def check_cut(sequence: Sequence, cuts: list[ShotCut]) -> None:
    """Raise PipelineError if the cut can't be published: no shots, or strips that don't fit."""
    if not cuts:
        raise PipelineError("The cut has no shots yet. Add one with Pipeline > Add Shot.")
    shots = {str(shot.code) for shot in sequence.shots(include_omitted=True)}
    unknown = [cut.shot for cut in cuts if cut.shot not in shots]
    if unknown:
        raise PipelineError(
            f"The cut has strips for {', '.join(unknown)}, which aren't shots in "
            f"{sequence.label}. Add shots with Pipeline > Add Shot."
        )
    for cut in cuts:
        if cut.frame_end < cut.frame_start or cut.cut_out - cut.cut_in != (
            cut.frame_end - cut.frame_start
        ):
            raise PipelineError(f"Shot {cut.shot}'s frame range doesn't match its strip.")


def apply_cut(sequence: Sequence, cuts: list[ShotCut]) -> CutChanges:
    """Write each shot's range, cut points and casting; mark shots with no strip omitted."""
    check_cut(sequence, cuts)
    shots = {str(shot.code): shot for shot in sequence.shots(include_omitted=True)}
    changes = CutChanges()
    in_cut = {cut.shot for cut in cuts}
    for cut in cuts:
        shot = shots[cut.shot]
        if shot.omitted:
            changes.restored.append(cut.shot)
        metadata = shot.metadata
        metadata.frame_start, metadata.frame_end = cut.frame_start, cut.frame_end
        metadata.cut_in, metadata.cut_out = cut.cut_in, cut.cut_out
        metadata.casting = list(cut.casting)
        metadata.omitted = False
        shot.save()
        changes.updated.append(cut.shot)
    for code, shot in sorted(shots.items()):
        if code not in in_cut and not shot.omitted:
            shot.omit()
            changes.omitted.append(code)
    return changes
