"""Where a sequence file renders, for the workfile's version: whichever task its cut is for.

Layout renders one playblast of the cut per sequence; animation a playblast per shot
(animation/blender/playblasts.py); lighting renders and comps per shot
(lighting/blender/renders.py). follow_version() sets the paths for the open file; the
session calls it on opening and saving, and New Node and Check Updates after they add
scenes.
"""

from __future__ import annotations

import contextlib

from ..animation.blender import playblasts
from ..common.errors import PipelineError
from ..lighting.blender import renders
from ..project.blender import nodes
from ..project.blender.nodes import ANIM, LAYOUT, LIGHT
from ..project.core.project import Project
from ..shots.blender import layout


def follow_version(project: Project, version: int) -> None:
    """Point the open sequence file's renders at this version's folders."""
    task = layout.cut_task()
    if task == ANIM:
        playblasts.set_playblast_paths(project, version)
    elif task == LIGHT:
        renders.set_render_paths(project, version)
    elif task == LAYOUT:
        with contextlib.suppress(PipelineError):  # A sequence that isn't in this project.
            master = layout.master_scene()
            node = nodes.sequence_node(master)
            assert node is not None  # master_scene holds one.
            layout.set_playblast_output(master, project.sequence(node.name), version)
