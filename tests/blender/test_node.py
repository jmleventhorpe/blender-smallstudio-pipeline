"""Runs inside Blender (see run.py): which node Publish works on."""

import bpy
import pytest
from conftest import add_cube

from smallstudio_pipeline.common.errors import PipelineError
from smallstudio_pipeline.project.blender.identity import create_root_collection
from smallstudio_pipeline.project.blender.nodes import find_node


@pytest.fixture
def two_assets(project):
    """Two asset roots in one scene, crate and barrel, a cube in each."""
    scene = bpy.context.scene
    crate = create_root_collection(project.create_asset("prop", "crate"), scene)
    barrel = create_root_collection(project.create_asset("prop", "barrel"), scene)
    return scene, add_cube(crate, "crate_box"), add_cube(barrel, "barrel_box")


def active(collection):
    view_layer = bpy.context.view_layer
    view_layer.active_layer_collection = view_layer.layer_collection.children[collection.name]


def test_the_active_node_wins(two_assets):
    scene, crate_box, _ = two_assets
    active(bpy.data.collections["barrel"])
    node = find_node(scene, bpy.context.view_layer, [crate_box])
    assert (node.kind, node.name) == ("asset", "barrel")


def test_else_the_node_holding_the_selection(two_assets):
    scene, crate_box, _ = two_assets
    node = find_node(scene, bpy.context.view_layer, [crate_box])
    assert (node.kind, node.name) == ("asset", "crate")


def test_else_the_only_node_or_a_message(two_assets):
    scene, _, barrel_box = two_assets
    with pytest.raises(PipelineError, match=r"several nodes \(.*\)\. Click one in the Outliner"):
        find_node(scene, bpy.context.view_layer, [])
    bpy.data.collections.remove(bpy.data.collections["crate"])
    assert find_node(scene, bpy.context.view_layer, []).name == "barrel"
    bpy.data.collections.remove(bpy.data.collections["barrel"])
    with pytest.raises(PipelineError, match="it has no node"):
        find_node(scene, bpy.context.view_layer, [barrel_box])
