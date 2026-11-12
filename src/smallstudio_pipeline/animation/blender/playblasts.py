"""Where an animation file's playblasts go: each shot's own render folder.

Playblasts are Blender's own viewport renders (View > Viewport Render Animation), written
to the scene's output path. set_playblast_paths() points every shot's animation scene at
shots/{shot}/anim/render/v###/, named after the shot and the workfile's version, so each
shot's playblast lands with that shot. The session sets it on opening, saving, building
and Check Updates.
"""

from __future__ import annotations

import bpy

from ...project.blender import nodes
from ...project.blender.nodes import ANIM
from ...project.core.project import Project


def set_playblast_paths(project: Project, version: int) -> None:
    """Point every shot's animation scene at this version's playblast folder."""
    label = f"v{version:0{project.config.version_padding}d}"
    for scene in bpy.data.scenes:
        node = nodes.shot_node(scene)
        if node is not None and node.task == ANIM:
            folder = project.shot(node.name).render_path(ANIM, version)
            scene.render.filepath = str(folder / f"{node.name}_{ANIM}_{label}_")
