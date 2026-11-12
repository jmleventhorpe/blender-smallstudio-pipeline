"""Making and editing nodes: New Node, the Nodes panel, and its Edit and Remove buttons.

New Node makes a node in the open file: an asset node, empty (an existing asset or a new
one, and its task), placed in the active collection so a prop can go inside its set's
node; a sequence node, which makes the scene on show the sequence's layout cut, its
shots' nodes coming from Add Shot; or a sequence's animation or lighting, which builds
its cut and a scene per shot from the layout or animation publish
(animation/blender/build.py, lighting/blender/build.py). The Nodes panel
lists the scene's nodes with their asset and task, flags two nodes that would publish
over each other, and edits or removes them (removing keeps the collection and its
contents).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import bpy
from bpy.props import EnumProperty, StringProperty

from ..animation.blender import build
from ..common.errors import PipelineError
from ..lighting.blender import build as lighting
from ..project.blender import nodes
from ..project.blender.identity import TASK
from ..project.core.project import Project
from ..session import state
from ..shots.blender import layout
from . import browse
from .common import has_project
from .panels import both_sidebars, wrapped

KINDS = [
    ("ASSET", "Asset", "A node for an asset's task"),
    ("SEQUENCE", "Sequence", "A sequence's layout cut"),
    ("ANIMATION", "Animation", "A sequence's animation, its shots linked from its layout"),
    ("LIGHTING", "Lighting", "A sequence's lighting, its shots linked from its animation"),
]
ICONS: dict[str, Any] = {
    "asset": "OUTLINER_COLLECTION",
    "sequence": "SEQUENCE",
    "shot": "SCENE_DATA",
}


def _asset_changed(operator: Any, context: bpy.types.Context | None) -> None:
    operator.task = browse.node_task_items(operator, context)[0][0]


class PIPELINE_OT_new_node(bpy.types.Operator):
    """Make a node in this file: an asset's, for a task, a sequence's cut, or its animation"""

    bl_idname = "pipeline.new_node"
    bl_label = "New Node"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(name="Kind", items=KINDS)
    asset: EnumProperty(name="Asset", items=browse.node_asset_items, update=_asset_changed)
    asset_type: EnumProperty(name="Type", items=browse.asset_type_items, update=_asset_changed)
    name: StringProperty(name="Name", description="Lowercase, e.g. street_lamp")
    task: EnumProperty(name="Task", items=browse.node_task_items)
    sequence: EnumProperty(name="Sequence", items=browse.node_sequence_items)
    episode: EnumProperty(name="Episode", items=browse.episode_items)
    title: StringProperty(name="Title", description="What happens in it, e.g. Opening chase")

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return has_project(cls)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        column = self.layout.column()
        column.prop(self, "kind", expand=True)
        project = state.current.project
        if self.kind == "ASSET":
            column.prop(self, "asset")
            if self.asset == browse.NEW:
                column.prop(self, "asset_type")
                column.prop(self, "name")
            column.prop(self, "task")
        elif self.kind == "SEQUENCE":
            column.prop(self, "sequence")
            if self.sequence == browse.NEW:
                if project is not None and project.config.episodes:
                    column.prop(self, "episode")
                column.prop(self, "title")
            wrapped(column, "The scene on show becomes the sequence's cut.", icon="INFO")
        else:
            column.prop(self, "sequence")
            source = "layout" if self.kind == "ANIMATION" else "animation"
            wrapped(
                column,
                f"The scene on show becomes the sequence's {self.kind.lower()} cut, with a "
                f"scene per shot linked from its {source} publish.",
                icon="INFO",
            )

    def execute(self, context: bpy.types.Context) -> set[str]:
        project = state.current.project
        assert project is not None  # Checked by poll.
        try:
            if self.kind == "ASSET":
                made = self.make_asset_node(context, project)
            elif self.kind == "SEQUENCE":
                made = self.make_sequence_node(context, project)
            else:
                made = self.make_from_publish(context, project)
        except PipelineError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Made {made}.")
        return {"FINISHED"}

    def make_asset_node(self, context: bpy.types.Context, project: Project) -> str:
        """An empty node for an asset's task, inside the active collection."""
        if self.asset == browse.NEW:
            asset = project.create_asset(self.asset_type, self.name.strip())
        else:
            asset = project.asset(self.asset)
        if self.task not in asset.settings.tasks:
            raise PipelineError(
                f"{asset.name} is a {asset.asset_type}: it has no {self.task} task."
            )
        if not asset.has_task(self.task):
            asset.add_task(self.task)  # An optional task, such as a prop's rig.
        active = context.view_layer.active_layer_collection
        parent = active.collection if active else None
        nodes.create_asset_node(asset, self.task, context.scene, parent)
        return f"{asset.name}'s {self.task} node"

    def make_sequence_node(self, context: bpy.types.Context, project: Project) -> str:
        """A sequence's node, making the scene on show its cut."""
        if layout.has_cut():
            raise PipelineError("This file already holds a sequence's cut: one per file.")
        if self.sequence == browse.NEW:
            episode = None
            if project.config.episodes:
                episode = project.next_episode() if self.episode == browse.NEW else self.episode
            sequence = project.create_sequence(episode, self.title)
        else:
            sequence = project.sequence(self.sequence)
        layout.start_cut(context.scene, sequence)
        return f"sequence {sequence.name}'s node, with its cut"

    def make_from_publish(self, context: bpy.types.Context, project: Project) -> str:
        """A sequence's animation or lighting cut, a scene per shot linked from the publish
        before it (layout's or animation's)."""
        what = self.kind.lower()
        if layout.has_cut():
            raise PipelineError("This file already holds a sequence's cut: one per file.")
        if self.sequence == browse.NEW:
            raise PipelineError(f"Pick a sequence: {what} starts from one already published.")
        sequence = project.sequence(self.sequence)
        if self.kind == "ANIMATION":
            build.build_animation(context.scene, sequence)
        else:
            lighting.build_lighting(context.scene, sequence)
        count = len(layout.shot_strips(context.scene))
        return f"{sequence.name}'s {what}, {count} shot{'s' if count != 1 else ''}"


def node_named(context: bpy.types.Context, name: str) -> nodes.Node | None:
    """The scene's node whose collection has this name."""
    return next((n for n in nodes.nodes_in(context.scene) if n.root.name == name), None)


class PIPELINE_OT_edit_node(bpy.types.Operator):
    """Change which task this asset node is for"""

    bl_idname = "pipeline.edit_node"
    bl_label = "Edit Node"
    bl_options = {"REGISTER", "UNDO"}

    node: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    asset: StringProperty(options={"HIDDEN", "SKIP_SAVE"})  # node_task_items reads these.
    asset_type: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    task: EnumProperty(name="Task", items=browse.node_task_items)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        found = node_named(context, self.node)
        if found is None or found.kind != "asset":
            return {"CANCELLED"}
        self.asset, self.asset_type = found.name, found.asset_type
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context) -> set[str]:
        found, project = node_named(context, self.node), state.current.project
        if found is None or found.kind != "asset" or project is None:
            return {"CANCELLED"}
        asset = project.asset(found.name)
        if not asset.has_task(self.task):
            asset.add_task(self.task)
        found.root[TASK] = self.task
        return {"FINISHED"}


class PIPELINE_OT_remove_node(bpy.types.Operator):
    """Make this node a plain collection again; its contents stay"""

    bl_idname = "pipeline.remove_node"
    bl_label = "Remove Node"
    bl_options = {"REGISTER", "UNDO"}

    node: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        found = node_named(context, self.node)
        if found is None:
            return {"CANCELLED"}
        nodes.unmake_node(found.root)
        return {"FINISHED"}


class PIPELINE_OT_activate_node(bpy.types.Operator):
    """Make this node the active collection: what Publish works on"""

    bl_idname = "pipeline.activate_node"
    bl_label = "Choose Node"
    bl_options = {"REGISTER", "INTERNAL"}

    node: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        found = node_named(context, self.node)
        if found is None:
            return {"CANCELLED"}
        nodes.make_active(context.scene, found.root)
        nodes.picked = "collection"
        return {"FINISHED"}


def describe(node: nodes.Node) -> str:
    """e.g. "character · rig", "sequence · layout", "shot · anim"."""
    if node.kind == "asset":
        return f"{node.asset_type} · {node.task or 'no task'}"
    return f"{node.kind} · {node.task}"


class NodesPanel:
    """The scene's nodes: what each is, and which one Publish works on."""

    bl_label = "Nodes"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return state.current.project is not None

    def draw(self: Any, context: bpy.types.Context) -> None:
        layout_, found = self.layout, nodes.nodes_in(context.scene)
        try:
            chosen = nodes.current_node(context).root
        except PipelineError:
            chosen = None
        same = Counter((n.name, n.task) for n in found if n.kind == "asset")
        for node in found:
            row = layout_.row(align=True)
            pick = row.operator(
                "pipeline.activate_node",
                text=node.root.name,
                icon=ICONS[node.kind],
                depress=node.root == chosen,
            )
            pick.node = node.root.name
            row.label(text=describe(node))
            if node.kind == "asset":
                row.operator(
                    "pipeline.edit_node", text="", icon="PREFERENCES"
                ).node = node.root.name
            row.operator("pipeline.remove_node", text="", icon="X").node = node.root.name
            if node.kind == "asset" and same[(node.name, node.task)] > 1:
                message = f"Two {node.name} {node.task} nodes would publish over each other."
                wrapped(layout_, message, icon="ERROR", alert=True)
        if not found:
            wrapped(layout_, "No nodes yet: New Node makes one.", icon="INFO")
        layout_.operator("pipeline.new_node", text="New Node…", icon="ADD")


CLASSES = (
    PIPELINE_OT_new_node,
    PIPELINE_OT_edit_node,
    PIPELINE_OT_remove_node,
    PIPELINE_OT_activate_node,
    *both_sidebars(NodesPanel, "nodes"),
)
