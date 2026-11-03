"""Runs inside Blender (see run.py): New Sequence, and Add Shot and Omit Shot in the cut."""

from pathlib import Path

import bpy
import pytest

from smallstudio_pipeline.blender.shots import layout


@pytest.fixture
def sequence(project):
    """Sequence 010_010's layout v001, open, from New Sequence."""
    assert bpy.ops.pipeline.new_sequence(episode="NEW", position="END") == {"FINISHED"}
    return project.sequence("010_010")


def cut():
    """(shot code, first frame in the cut, length) per strip, in order."""
    strips = layout.shot_strips(layout.master_scene())
    return [(layout.strip_shot(s), s.left_handle, s.duration) for s in strips]


def add_shot_at(frame):
    layout.master_scene().frame_current = frame
    assert bpy.ops.pipeline.add_shot() == {"FINISHED"}


def test_new_sequence_opens_its_layout_with_an_empty_cut(project, sequence):
    assert Path(bpy.data.filepath) == sequence.workfile_path("layout", 1)
    master = layout.master_scene()
    assert master.name == "010_010" and master[layout.SEQUENCE] == "010_010"
    assert cut() == []
    bpy.ops.pipeline.new_sequence(episode="010", position="END")
    assert [str(seq.code) for seq in project.sequences()] == ["010_010", "010_020"]


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
    master.sequence_editor.active_strip = layout.shot_strips(master)[1]
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


def test_omit_shot_needs_a_shot_strip_selected(sequence):
    add_shot_at(1)
    layout.master_scene().sequence_editor.active_strip = None
    assert not bpy.ops.pipeline.omit_shot.poll()
