"""Runs inside Blender (see run.py): publishing a sequence's layout."""

import json
from pathlib import Path

import bpy
import pytest
from conftest import place, publish_model, publish_prop

from smallstudio_pipeline.blender.identity import INSTANCE_ID
from smallstudio_pipeline.blender.shots import layout
from smallstudio_pipeline.blender.ui import results
from smallstudio_pipeline.core.metadata import CastEntry


@pytest.fixture
def cut(project):
    """Sequence 010_010's layout file with two shots: hero in 0010, two crates in 0020."""
    publish_model(project)
    publish_prop(project, "crate")
    bpy.ops.pipeline.new_sequence(episode="NEW")
    bpy.ops.pipeline.add_shot()
    layout.master_scene().frame_current = 1000
    bpy.ops.pipeline.add_shot()
    place(project, bpy.data.scenes["010_010_0010"], "hero")
    place(project, bpy.data.scenes["010_010_0020"], "crate")
    place(project, bpy.data.scenes["010_010_0020"], "crate", location=(3.0, 0.0, 0.0))
    return project.sequence("010_010")


def test_a_layout_publish_copies_the_file_and_writes_the_cut(project, cut):
    workfile = Path(bpy.data.filepath)
    assert bpy.ops.pipeline.publish() == {"FINISHED"}
    assert results.last is not None and results.last.published == "010_010_layout v001"

    assert Path(bpy.data.filepath) == workfile  # Still on the workfile.
    assert cut.publish_path("layout", 1).is_file() and cut.hero_path("layout").is_file()
    record = json.loads(cut.hero_path("layout").with_suffix(".json").read_text())
    assert (record["entity_kind"], record["entity"], record["version"]) == (
        "sequence",
        "010_010",
        1,
    )
    assert sorted(d["path"] for d in record["dependencies"]) == [
        "assets/character/hero/model/publish/hero_model.blend",
        "assets/prop/crate/model/publish/crate_model.blend",
    ]
    assert record["checks"]["010_010_0010/ShotCamera"] == "passed"
    assert not any("AssetRoot" in check for check in record["checks"])

    first, second = project.shot("010_010_0010"), project.shot("010_010_0020")
    assert first.frame_range == (101, 148) and second.frame_range == (101, 148)
    assert (second.metadata.cut_in, second.metadata.cut_out) == (49, 96)
    assert first.metadata.casting == [CastEntry("hero", "hero_01")]
    assert second.metadata.casting == [
        CastEntry("crate", "crate_01"),
        CastEntry("crate", "crate_02"),
    ]


def test_the_published_file_holds_every_scene(project, cut):
    bpy.ops.pipeline.publish()
    bpy.ops.wm.open_mainfile(filepath=str(cut.hero_path("layout")))
    assert {scene.name for scene in bpy.data.scenes} == {"010_010", "010_010_0010", "010_010_0020"}
    assert [layout.strip_shot(s) for s in layout.shot_strips(layout.master_scene())] == [
        "010_010_0010",
        "010_010_0020",
    ]


def test_a_strip_removed_by_hand_omits_its_shot(project, cut):
    master = layout.master_scene()
    master.sequence_editor.strips.remove(layout.shot_strips(master)[1])
    bpy.ops.pipeline.publish()
    assert project.shot("010_010_0020").omitted
    assert not project.shot("010_010_0010").omitted


def test_duplicate_instance_ids_block_until_fixed(project, cut):
    bpy.ops.wm.save_mainfile()  # Numbers the crates 01 and 02.
    crates = [o for o in bpy.data.scenes["010_010_0020"].objects if o.get(INSTANCE_ID)]
    crates[1][INSTANCE_ID] = crates[0][INSTANCE_ID]  # As Shift+D would.

    with pytest.raises(RuntimeError, match=r"Publish blocked \(010_010_0020: 3 passed, 1 failed\)"):
        bpy.ops.pipeline.publish()
    assert results.last is not None and results.last.published is None
    part = next(p for p in results.last.checked if p.label == "010_010_0020")
    assert part.report.get("UniqueInstanceIds").status == "failed"

    index = results.last.checked.index(part)
    assert bpy.ops.pipeline.fix_check(part=index, check_id="UniqueInstanceIds") == {"FINISHED"}
    assert part.report.get("UniqueInstanceIds").status == "fixed"
    assert sorted(o[INSTANCE_ID] for o in crates) == ["crate_01", "crate_02"]
    assert bpy.ops.pipeline.publish() == {"FINISHED"}


def test_a_shot_without_a_camera_blocks(project, cut):
    bpy.data.scenes["010_010_0010"].camera = None
    with pytest.raises(RuntimeError, match="Publish blocked"):
        bpy.ops.pipeline.publish()
    assert results.last is not None
    assert results.last.summary() == "010_010_0010: 3 passed, 1 failed"


def test_an_empty_cut_cant_be_published(project):
    bpy.ops.pipeline.new_sequence(episode="NEW")
    with pytest.raises(RuntimeError, match="The cut has no shots yet"):
        bpy.ops.pipeline.publish()
    assert not project.sequence("010_010").hero_path("layout").exists()
