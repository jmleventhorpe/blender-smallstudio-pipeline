"""The node: the root collection Publish works on.

Everything that publishes has a root collection, so publishing works the same way in
every file: an asset's root (carrying its identity), a sequence's root in a layout file's
master scene, and a shot's root in its scene. A shot's root publishes its sequence's
layout, with that shot first.

The node is the active collection in the Outliner when it's a root (the one you clicked);
else the root holding the selected objects (the innermost, for a prop inside its set);
else the scene's only root. node_label() says which, for the Publish panel.
"""

from __future__ import annotations

from dataclasses import dataclass

import bpy

from ...common.errors import PipelineError
from ...project.blender.identity import asset_identity
from ...project.core.entities import Sequence
from ...project.core.project import Project
from ...shots.blender.layout import LAYOUT, SEQUENCE, SHOT
from ...workfiles.core.context import FileContext


@dataclass(frozen=True)
class Node:
    root: bpy.types.Collection
    kind: str  # "asset", "sequence" or "shot".
    name: str  # The asset's name, or the sequence's or shot's code.


def node_of(collection: bpy.types.Collection | None) -> Node | None:
    """The node a collection is, if it's a root."""
    if collection is None or collection.library is not None:
        return None
    identity = asset_identity(collection)
    if identity is not None:
        return Node(collection, "asset", identity[0])
    for key, kind in ((SEQUENCE, "sequence"), (SHOT, "shot")):
        if key in collection:
            return Node(collection, kind, str(collection[key]))
    return None


def roots(scene: bpy.types.Scene) -> list[Node]:
    """Every node in the scene."""
    found = [node_of(collection) for collection in scene.collection.children_recursive]
    return [node for node in found if node is not None]


def find_node(
    scene: bpy.types.Scene,
    view_layer: bpy.types.ViewLayer,
    selected: list[bpy.types.Object],
) -> Node:
    """The node to publish: the active root collection, else the selection's, else the only one."""
    active = view_layer.active_layer_collection
    node = node_of(active.collection if active else None)
    if node is not None:
        return node
    nodes = roots(scene)
    if selected:
        holding = [n for n in nodes if any(obj in n.root.all_objects[:] for obj in selected)]
        # A prop being edited inside its set is in both roots: the innermost one wins.
        inner = [
            n for n in holding if not any(o.root in n.root.children_recursive[:] for o in holding)
        ]
        if len(inner) == 1:
            return inner[0]
        if len(inner) > 1:
            names = ", ".join(n.root.name for n in inner)
            raise PipelineError(
                f"The selection is in several roots ({names}). Click one in the Outliner."
            )
    if len(nodes) == 1:
        return nodes[0]
    if not nodes:
        raise PipelineError("There's nothing to publish in this scene: it has no root collection.")
    names = ", ".join(n.root.name for n in nodes)
    raise PipelineError(f"This scene has several roots ({names}). Click one in the Outliner.")


def layout_sequence(project: Project, file: FileContext, node: Node) -> Sequence:
    """The sequence a sequence's or shot's node publishes: the open layout file's own."""
    code = node.name if node.kind == "sequence" else str(project.shot(node.name).code.sequence)
    if file.entity_kind != "sequence" or file.task != LAYOUT or file.entity != code:
        raise PipelineError(f"{node.root.name} publishes from sequence {code}'s layout workfile.")
    return project.sequence(code)


def current_node(context: bpy.types.Context) -> Node:
    """The node for the context's scene, view layer and selection."""
    return find_node(context.scene, context.view_layer, list(context.selected_objects or ()))
