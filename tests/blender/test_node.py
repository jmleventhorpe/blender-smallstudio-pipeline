"""Runs inside Blender (see run.py): which node Publish works on."""

import bpy
import pytest
from conftest import add_cube, make_cut, place, publish_model

from smallstudio_pipeline.common.errors import PipelineError
from smallstudio_pipeline.project.blender.identity import create_root_collection
from smallstudio_pipeline.project.blender.nodes import LoadedPicked, find_node


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


def test_the_selection_wins_when_picked_last(two_assets):
    scene, crate_box, _ = two_assets
    active(bpy.data.collections["barrel"])
    node = find_node(scene, bpy.context.view_layer, [crate_box], prefer="selection")
    assert node.name == "crate"
    assert find_node(scene, bpy.context.view_layer, [], prefer="selection").name == "barrel"


def test_a_loaded_asset_isnt_published_here(project):
    publish_model(project)
    make_cut()
    bpy.ops.pipeline.add_shot()
    scene = bpy.data.scenes["010_010_0010"]
    place(project, scene, "hero")
    empty = next(o for o in scene.objects if o.instance_type == "COLLECTION")
    view_layer = scene.view_layers[0]
    with pytest.raises(LoadedPicked, match="publish it from its own file"):
        find_node(scene, view_layer, [empty], prefer="selection")
    assert find_node(scene, view_layer, [empty]).kind == "shot"  # The shot node was clicked.


def test_the_watcher_notes_what_was_picked_last(two_assets):
    from smallstudio_pipeline.project.blender import nodes
    from smallstudio_pipeline.session.handlers import watch_picks

    _, crate_box, _ = two_assets
    watch_picks()
    crate_box.select_set(True)
    watch_picks()
    assert nodes.picked == "selection"
    active(bpy.data.collections["barrel"])
    watch_picks()
    assert nodes.picked == "collection"
