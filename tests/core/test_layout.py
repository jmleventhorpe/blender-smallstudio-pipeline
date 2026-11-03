import pytest

from smallstudio_pipeline.core.errors import PipelineError
from smallstudio_pipeline.core.layout import ShotCut, apply_cut
from smallstudio_pipeline.core.metadata import CastEntry


@pytest.fixture
def sequence(project):
    sequence = project.create_sequence("010")
    for _ in range(3):
        sequence.create_shot()
    return sequence


def cut(code, start, length, cut_in, casting=()):
    return ShotCut(code, start, start + length - 1, cut_in, cut_in + length - 1, casting)


def test_the_cut_is_written_into_each_shots_metadata(project, sequence):
    hero = CastEntry("hero", "hero_01")
    changes = apply_cut(
        sequence,
        [
            cut("010_010_0010", 101, 48, 1, (hero,)),
            cut("010_010_0020", 101, 24, 49),
            cut("010_010_0030", 101, 30, 73),
        ],
    )
    assert changes.updated == ["010_010_0010", "010_010_0020", "010_010_0030"]
    shot = project.shot("010_010_0010")
    assert shot.frame_range == (101, 148)
    assert (shot.metadata.cut_in, shot.metadata.cut_out) == (1, 48)
    assert shot.metadata.casting == [hero]


def test_shots_without_a_strip_are_omitted_and_come_back(project, sequence):
    changes = apply_cut(sequence, [cut("010_010_0010", 101, 48, 1)])
    assert changes.omitted == ["010_010_0020", "010_010_0030"]
    assert changes.summary == "1 shots; omitted 010_010_0020, 010_010_0030"
    assert project.shot("010_010_0020").omitted

    changes = apply_cut(
        sequence, [cut("010_010_0010", 101, 48, 1), cut("010_010_0020", 101, 24, 49)]
    )
    assert changes.restored == ["010_010_0020"]
    assert not project.shot("010_010_0020").omitted
    assert changes.omitted == []  # 0030 was already omitted.


def test_strips_for_unknown_shots_are_refused(sequence):
    with pytest.raises(PipelineError, match="010_010_0090, which aren't shots"):
        apply_cut(sequence, [cut("010_010_0090", 101, 24, 1)])


def test_a_range_that_doesnt_match_its_strip_is_refused(sequence):
    with pytest.raises(PipelineError, match="0010's frame range doesn't match"):
        apply_cut(sequence, [ShotCut("010_010_0010", 101, 148, 1, 24)])
