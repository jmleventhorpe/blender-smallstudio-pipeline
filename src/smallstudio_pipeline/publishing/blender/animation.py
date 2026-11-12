"""Publishing a sequence's animation: each shot's animation node, for lighting to link.

An animation publish writes every shot's animation node in the cut ("010_010_0010.anim",
holding layout's shot node overridden and keyed) with bpy.data.libraries.write: the
versioned file, and the hero through a temp file and a rename. Overrides and their
actions come through, linking back to the layout publish and the assets (spike T14).
Checks run once per shot, as for layout, plus the cast against layout's.
"""

from __future__ import annotations

import bpy

from ...common.files import replace_with_retry
from ...project.blender import nodes
from ...shots.blender import layout
from ..core.publishing import PublishPlan


def shot_roots(master: bpy.types.Scene) -> list[bpy.types.Collection]:
    """Each shot's animation node in the cut, in cut order."""
    roots = []
    for strip in layout.shot_strips(master):
        node = nodes.shot_node(strip.scene)
        assert node is not None  # shot_strips only returns strips showing a shot.
        roots.append(node.root)
    return roots


def write_animation(plan: PublishPlan, roots: list[bpy.types.Collection]) -> None:
    """Write the shots' animation nodes as the hero and the versioned file."""
    plan.hero.parent.mkdir(parents=True, exist_ok=True)
    # The temp file sits beside the hero so relative paths and the rename both hold.
    temp = plan.hero.with_name(f"{plan.hero.stem}.tmp.blend")
    bpy.data.libraries.write(str(temp), set(roots), path_remap="RELATIVE_ALL")
    replace_with_retry(temp, plan.hero)
    bpy.data.libraries.write(str(plan.path), set(roots), path_remap="RELATIVE_ALL")
