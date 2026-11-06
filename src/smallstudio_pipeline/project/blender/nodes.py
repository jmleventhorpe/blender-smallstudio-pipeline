"""Nodes: the root collections that say what a file is working on.

Everything that publishes is a node, a collection carrying what it is (see identity.py):
an asset node its asset, type and task; a sequence node its sequence; a shot node its
shot. Scenes carry nothing: a shot's scene is the one holding its node, and the cut is the
scene holding the sequence node. Only a file's own collections are nodes; a linked
asset's root, or an override of one, is an instance (loading/blender/instances.py).

The node Publish works on (current_node) is the active collection in the Outliner when
it's a node (the one you clicked); else the node holding the selected objects (the
innermost, for a prop inside its set); else the scene's only node.
"""

from __future__ import annotations

from dataclasses import dataclass

import bpy

from ...common.errors import PipelineError
from ..core.entities import Sequence
from ..core.project import Project
from .identity import SEQUENCE, SHOT, TASK, asset_identity


@dataclass(frozen=True)
class Node:
    root: bpy.types.Collection
    kind: str  # "asset", "sequence" or "shot".
    name: str  # The asset's name, or the sequence's or shot's code.
    asset_type: str = ""  # Assets only.
    task: str = ""  # Assets only: the task the node is for, "" if it hasn't one yet.


def node_of(collection: bpy.types.Collection | None) -> Node | None:
    """The node a collection is, if it's one of this file's."""
    if collection is None or collection.library or collection.override_library:
        return None
    identity = asset_identity(collection)
    if identity is not None:
        task = collection.get(TASK, "")
        return Node(collection, "asset", *identity, task=task if isinstance(task, str) else "")
    if SEQUENCE in collection:
        return Node(collection, "sequence", str(collection[SEQUENCE]))
    if SHOT in collection:
        return Node(collection, "shot", str(collection[SHOT]))
    return None


def nodes_in(scene: bpy.types.Scene) -> list[Node]:
    """Every node in a scene."""
    found = [node_of(collection) for collection in scene.collection.children_recursive]
    return [node for node in found if node is not None]


def node_holding(obj: bpy.types.Object | None, scene: bpy.types.Scene) -> Node | None:
    """The innermost node an object is in, if any."""
    if obj is None:
        return None
    holding = [node for node in nodes_in(scene) if obj in node.root.all_objects[:]]
    inner = [n for n in holding if not any(o.root in n.root.children_recursive[:] for o in holding)]
    return inner[0] if inner else None


def find_node(
    scene: bpy.types.Scene, view_layer: bpy.types.ViewLayer, selected: list[bpy.types.Object]
) -> Node:
    """The node to publish: the active node collection, else the selection's, else the only one."""
    active = view_layer.active_layer_collection
    node = node_of(active.collection if active else None)
    if node is not None:
        return node
    nodes = nodes_in(scene)
    if selected:
        holding = {found for obj in selected if (found := node_holding(obj, scene))}
        if len(holding) == 1:
            return holding.pop()
        if len(holding) > 1:
            names = ", ".join(sorted(n.root.name for n in holding))
            raise PipelineError(
                f"The selection is in several nodes ({names}). Click one in the Outliner."
            )
    if len(nodes) == 1:
        return nodes[0]
    if not nodes:
        raise PipelineError(
            "There's nothing to publish in this scene: it has no node. Make one with New Node."
        )
    names = ", ".join(n.root.name for n in nodes)
    raise PipelineError(f"This scene has several nodes ({names}). Click one in the Outliner.")


def current_node(context: bpy.types.Context) -> Node:
    """The node for the context's scene, view layer and selection."""
    return find_node(context.scene, context.view_layer, list(context.selected_objects or ()))


def node_sequence(project: Project, node: Node) -> Sequence:
    """The sequence a sequence's or shot's node belongs to."""
    if node.kind == "sequence":
        return project.sequence(node.name)
    return project.sequence(str(project.shot(node.name).code.sequence))


def shot_node(scene: bpy.types.Scene | None) -> Node | None:
    """The shot node a scene holds at its top, if it's a shot's scene."""
    for collection in scene.collection.children if scene else ():
        node = node_of(collection)
        if node is not None and node.kind == "shot":
            return node
    return None


def sequence_node(scene: bpy.types.Scene | None) -> Node | None:
    """The sequence node a scene holds at its top, if it's a cut."""
    for collection in scene.collection.children if scene else ():
        node = node_of(collection)
        if node is not None and node.kind == "sequence":
            return node
    return None


def create_node(scene: bpy.types.Scene, name: str, key: str, value: str) -> bpy.types.Collection:
    """A new node in a scene, made its active collection so new things land in it."""
    root = bpy.data.collections.new(name)
    root[key] = value
    scene.collection.children.link(root)
    make_active(scene, root)
    return root


def make_active(scene: bpy.types.Scene, collection: bpy.types.Collection) -> None:
    """Make a collection at the top of a scene its active collection, in every view layer."""
    for view_layer in scene.view_layers:
        if view_layer.layer_collection is None:  # A new scene's, until Blender updates it.
            view_layer.update()
        found = (
            view_layer.layer_collection.children.get(collection.name)
            if view_layer.layer_collection
            else None
        )
        if found is not None:
            view_layer.active_layer_collection = found


def adopt_scene_identity() -> None:
    """Move identity off scenes onto nodes, for files from before nodes carried it.

    A scene with a sequence or shot code gets that node if it hasn't one (a shot's takes the
    scene's loose objects), then loses the code.
    """
    for scene in bpy.data.scenes:
        for key, finder in ((SEQUENCE, sequence_node), (SHOT, shot_node)):
            if key not in scene:
                continue
            code = str(scene[key])
            if finder(scene) is None:
                root = create_node(scene, code, key, code)
                if key == SHOT:
                    for obj in list(scene.collection.objects):
                        root.objects.link(obj)
                        scene.collection.objects.unlink(obj)
            del scene[key]


def give_tasks(asset: str, task: str) -> None:
    """Give an asset's nodes with no task this one (files from before nodes had tasks)."""
    for scene in bpy.data.scenes:
        for node in nodes_in(scene):
            if node.kind == "asset" and node.name == asset and not node.task:
                node.root[TASK] = task
