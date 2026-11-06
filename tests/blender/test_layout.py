"""Runs inside Blender (see run.py): New Sequence, and Add Shot and Omit Shot in the cut."""

from pathlib import Path
from types import SimpleNamespace

import bpy
import pytest
from conftest import make_cut

from smallstudio_pipeline.interface import browse
from smallstudio_pipeline.project.blender import nodes
from smallstudio_pipeline.project.blender.identity import SEQUENCE, SHOT
from smallstudio_pipeline.shots.blender import layout


@pytest.fixture
def sequence(project):
    """Sequence 010_010's layout v001, open, from New Sequence."""
    make_cut()
    return project.sequence("010_010")


def cut():
    """(shot code, first frame in the cut, length) per strip, in order."""
    strips = layout.shot_strips(layout.master_scene())
    return [(layout.strip_shot(s), s.left_handle, s.duration) for s in strips]


def add_shot_at(frame):
    layout.master_scene().frame_current = frame
    assert bpy.ops.pipeline.add_shot() == {"FINISHED"}


def test_a_sequence_node_makes_the_scene_its_cut(project, sequence):
    assert Path(bpy.data.filepath) == sequence.workfile_path("layout", 1)
    master = layout.master_scene()
    node = nodes.sequence_node(master)
    assert master.name == "010_010" and node is not None and node.name == "010_010"
    assert not master.keys()  # Scenes carry nothing; the node does.
    assert cut() == []
    assert master.render.fps == 24 and master.render.resolution_x == 1920
    with pytest.raises(RuntimeError, match="already holds a sequence's cut"):
        bpy.ops.pipeline.new_node(kind="SEQUENCE", sequence="NEW", episode="010")
    make_cut(title="Opening chase")  # Another file, another sequence.
    assert [str(seq.code) for seq in project.sequences()] == ["010_010", "020_010"]
    assert project.sequence("020_010").title == "Opening chase"


def test_added_shots_get_a_scene_a_camera_and_the_shot_start(project, sequence):
    add_shot_at(1)
    add_shot_at(1000)
    assert cut() == [("010_010_0010", 1, 48), ("010_010_0020", 49, 48)]
    scene = bpy.data.scenes["010_010_0010"]
    assert (scene.frame_start, scene.frame_end) == (101, 148)
    assert scene.camera is not None and scene.camera.name == "010_010_0010_cam"
    assert scene.render.fps == 24
    assert project.shot("010_010_0020").sequence == sequence
    assert layout.master_scene().frame_end == 96


def test_a_shot_added_mid_cut_goes_between_and_moves_later_strips(sequence):
    add_shot_at(1)
    add_shot_at(1000)
    add_shot_at(10)  # The playhead is in 0010.
    assert cut() == [("010_010_0010", 1, 48), ("010_010_0015", 49, 48), ("010_010_0020", 97, 48)]


def test_a_shot_added_before_the_first_goes_first(sequence):
    add_shot_at(1)
    add_shot_at(0)
    assert cut() == [("010_010_0005", 1, 48), ("010_010_0010", 49, 48)]


def test_omitting_a_shot_closes_the_gap_and_keeps_its_scene(project, sequence):
    for _ in range(3):
        add_shot_at(1000)
    master = layout.master_scene()
    strips = layout.shot_strips(master)
    assert master.sequence_editor.active_strip == strips[2]  # The shot just added.
    strips[2].select = False
    strips[1].select = True  # Selected, not made active.
    assert bpy.ops.pipeline.omit_shot() == {"FINISHED"}
    assert cut() == [("010_010_0010", 1, 48), ("010_010_0030", 49, 48)]
    assert project.shot("010_010_0020").omitted
    assert "010_010_0020" in bpy.data.scenes
    add_shot_at(1000)  # Omitted shots keep their numbers.
    assert cut()[-1][0] == "010_010_0040"


def test_retiming_in_the_cut_becomes_the_shots_range(sequence):
    add_shot_at(1)
    add_shot_at(1000)
    first = layout.shot_strips(layout.master_scene())[0]
    first.left_handle_offset = 4  # Trim four frames off the head of 0010.
    first.content_start -= 4  # And slide it back to the start of the cut.
    layout.sync_ranges(layout.master_scene())
    scene = bpy.data.scenes["010_010_0010"]
    assert (scene.frame_start, scene.frame_end) == (105, 148)
    assert (first.left_handle, first.duration) == (1, 44)
    assert first.left_handle_offset == 0


def test_shot_actions_only_work_in_a_layout_workfile(project):
    project.create_asset("prop", "crate")
    bpy.ops.pipeline.new_workfile(category="prop", entity="crate", task="model")
    assert not bpy.ops.pipeline.add_shot.poll()
    assert not bpy.ops.pipeline.omit_shot.poll()


def test_omit_shot_needs_one_shot_strip_selected(sequence):
    add_shot_at(1)
    add_shot_at(1000)
    master = layout.master_scene()
    master.sequence_editor.active_strip = None
    for strip in layout.shot_strips(master):
        strip.select = False
    assert not bpy.ops.pipeline.omit_shot.poll()
    for strip in layout.shot_strips(master):
        strip.select = True
    assert not bpy.ops.pipeline.omit_shot.poll()  # Two selected, neither active.
    master.sequence_editor.active_strip = layout.shot_strips(master)[0]
    assert bpy.ops.pipeline.omit_shot.poll()  # The active one of those selected.


def test_every_workspaces_sequencer_edits_the_cut(sequence):
    master = layout.master_scene()
    assert bpy.data.workspaces and all(w.sequencer_scene == master for w in bpy.data.workspaces)


def test_the_playblast_goes_to_the_layout_render_folder_for_each_version(project, sequence):
    master = layout.master_scene()
    folder = sequence.render_path("layout", 1)
    assert master.render.filepath == str(folder / "010_010_layout_")
    bpy.ops.pipeline.version_up()
    folder = sequence.render_path("layout", 2)
    assert layout.master_scene().render.filepath == str(folder / "010_010_layout_")
    assert "sequences/010_010/layout/render/v002" in folder.as_posix()


def test_sequence_titles_show_beside_their_codes_in_the_dialogs(project, sequence):
    project.create_sequence("010", title="Opening chase")
    choices = browse.entity_items(SimpleNamespace(category="sequence"), bpy.context)
    assert [(code, label) for code, label, _ in choices] == [
        ("010_010", "010_010"),
        ("010_020", "010_020  Opening chase"),
    ]


def test_each_shot_has_a_node_holding_its_camera_as_the_active_collection(sequence):
    add_shot_at(1)
    scene = bpy.data.scenes["010_010_0010"]
    node = nodes.shot_node(scene)
    assert node is not None and (node.root.name, node.name) == ("010_010_0010", "010_010_0010")
    assert scene.camera.name in node.root.objects and not scene.keys()
    assert scene.view_layers[0].active_layer_collection.collection == node.root


def test_files_from_before_nodes_get_their_scenes_identity_moved_onto_nodes(sequence):
    add_shot_at(1)
    master, scene = layout.master_scene(), bpy.data.scenes["010_010_0010"]
    for each in (master, scene):  # As files saved before nodes carried everything.
        node = nodes.sequence_node(each) or nodes.shot_node(each)
        each.collection.children.unlink(node.root)
        for obj in list(node.root.objects):
            each.collection.objects.link(obj)
        bpy.data.collections.remove(node.root)
    master[SEQUENCE], scene[SHOT] = "010_010", "010_010_0010"

    nodes.adopt_scene_identity()

    shot = nodes.shot_node(scene)
    assert shot is not None and scene.camera.name in shot.root.objects
    assert not scene.collection.objects and not scene.keys() and not master.keys()
    assert nodes.sequence_node(master) is not None


def markers(scene):
    return sorted((marker.name, marker.frame) for marker in scene.timeline_markers)


def test_markers_follow_the_cut_and_leave_others_alone(project, sequence):
    master = layout.master_scene()
    master.timeline_markers.new("note", frame=5)
    add_shot_at(1)
    add_shot_at(1000)
    add_shot_at(10)
    assert markers(master) == [("0010", 1), ("0015", 49), ("0020", 97), ("note", 5)]
    assert markers(bpy.data.scenes["010_010_0015"]) == [("0015", 101)]

    strips = layout.shot_strips(master)
    for strip in strips:
        strip.select = strip == strips[1]
    bpy.ops.pipeline.omit_shot()
    assert markers(master) == [("0010", 1), ("0020", 49), ("note", 5)]


def test_the_label_names_the_shot_or_the_cut(sequence):
    from smallstudio_pipeline.interface.menu import scene_label

    add_shot_at(1)
    assert scene_label(bpy.data.scenes["010_010_0010"]) == " · shot 0010"
    assert scene_label(layout.master_scene()) == " · cut"
