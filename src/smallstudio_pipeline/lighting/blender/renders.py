"""Where a lighting file renders, and the comp scenes reading those renders.

Renders belong to shots: a shot's lighting scene writes shots/{shot}/light/render/v###/,
a multilayer EXR per frame named after the shot and the workfile's version, and its comp
scene writes the final frames to comp/ inside that folder. set_render_paths() points
every shot there for a version; the session sets it on opening, saving and building.

A comp scene's Image node reads its shot's lighting renders. Blender only shows a
multilayer EXR's passes once the files exist, and a link made before then stays on a
socket that reads nothing, so connect_renders() loads the renders and links Combined only
when they're there. It runs with set_render_paths() and before a comp scene renders.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import bpy

from ...project.blender import nodes
from ...project.blender.nodes import LIGHT
from ...project.core.project import Project

READER = "renders"  # The comp tree's Image node that reads the lighting renders.


def lit_scenes() -> dict[str, bpy.types.Scene]:
    """Each shot's lighting scene in the open file, by shot code."""
    found = {}
    for scene in bpy.data.scenes:
        node = nodes.shot_node(scene)
        if node is not None and node.task == LIGHT:
            found[node.name] = scene
    return found


def comp_of(code: str) -> bpy.types.Scene | None:
    """A shot's comp scene, by its name."""
    return bpy.data.scenes.get(f"{code}.comp")


def render_prefix(project: Project, code: str, version: int, comp: bool = False) -> Path:
    """A shot's lighting (or comp) renders for a version, before the frame number:
    shots/010_010_0010/light/render/v003/010_010_0010_light_v003_ (comp/…_comp_v003_)."""
    label = f"v{version:0{project.config.version_padding}d}"
    folder = project.shot(code).render_path(LIGHT, version)
    if comp:
        return folder / "comp" / f"{code}_comp_{label}_"
    return folder / f"{code}_{LIGHT}_{label}_"


def set_render_paths(project: Project, version: int) -> None:
    """Point every shot's lighting and comp scene at this version's render folder."""
    for code, scene in lit_scenes().items():
        prefix = render_prefix(project, code, version)
        scene.render.filepath = str(prefix)
        comp = comp_of(code)
        if comp is not None:
            comp.render.filepath = str(render_prefix(project, code, version, comp=True))
            connect_renders(comp, scene, prefix)


def connect_renders(comp: bpy.types.Scene, lit: bpy.types.Scene, prefix: Path) -> bool:
    """Have a comp scene read its shot's lighting renders, if they exist. True if it does."""
    first = Path(f"{prefix}{lit.frame_start:04d}.exr")
    effects: Any = comp.compositor_effects  # pyright: ignore[reportAttributeAccessIssue]
    tree: Any = effects.active.node_group if effects.active else None
    reader = tree.nodes.get(READER) if tree else None
    if reader is None or not first.is_file():
        return False
    image = next(
        (i for i in bpy.data.images if Path(bpy.path.abspath(i.filepath)) == first), None
    ) or bpy.data.images.load(str(first))
    image.source = "SEQUENCE"
    reader.image = image
    reader.frame_start = lit.frame_start
    reader.frame_duration = lit.frame_end - lit.frame_start + 1
    reader.frame_offset = lit.frame_start - 1  # The files are numbered by scene frame.
    for link in [link for link in tree.links if link.from_node == reader]:
        to_socket = link.to_socket
        tree.links.remove(link)
        tree.links.new(reader.outputs["Combined"], to_socket)
    return True
