import pytest

from smallstudio_pipeline.core.errors import NamingError
from smallstudio_pipeline.core.naming import (
    SequenceCode,
    ShotCode,
    check_name,
    next_number,
)


@pytest.mark.parametrize("name", ["hero", "hero_02", "street_lamp"])
def test_check_name_accepts_snake_case(name):
    assert check_name(name) == name


@pytest.mark.parametrize("name", ["Hero", "hero lamp", "2hero", "hero-lamp", "", "héro"])
def test_check_name_rejects_others(name):
    with pytest.raises(NamingError, match="lowercase"):
        check_name(name)


def test_check_name_uses_a_custom_pattern():
    assert check_name("HERO", pattern="[A-Z]+") == "HERO"
    with pytest.raises(NamingError, match=r"\[A-Z\]\+"):
        check_name("hero", pattern="[A-Z]+")


def test_shot_code_with_episodes_round_trips():
    code = ShotCode.parse("010_020_0030", episodes=True)
    assert code == ShotCode("010", "020", "0030")
    assert str(code) == "010_020_0030"
    assert str(code.sequence_code) == "010_020"


def test_shot_code_without_episodes_round_trips():
    code = ShotCode.parse("020_0030", episodes=False)
    assert code == ShotCode(None, "020", "0030")
    assert str(code) == "020_0030"
    assert str(code.sequence_code) == "020"


@pytest.mark.parametrize(
    ("text", "episodes"),
    [("020_0030", True), ("010_020_0030", False), ("010_020_030", True), ("010_02a_0030", True)],
)
def test_shot_code_rejects_wrong_shapes(text, episodes):
    with pytest.raises(NamingError, match="isn't a shot code"):
        ShotCode.parse(text, episodes)


def test_sequence_code_parses_both_shapes():
    assert SequenceCode.parse("010_020", episodes=True) == SequenceCode("010", "020")
    assert SequenceCode.parse("020", episodes=False) == SequenceCode(None, "020")
    with pytest.raises(NamingError):
        SequenceCode.parse("020", episodes=True)


def test_codes_sort_in_order():
    codes = [
        ShotCode.parse(text, True) for text in ("010_020_0030", "010_010_0020", "010_020_0015")
    ]
    assert [str(code) for code in sorted(codes)] == ["010_010_0020", "010_020_0015", "010_020_0030"]


def test_next_number_appends_in_steps():
    assert next_number([], step=10) == 10
    assert next_number([10, 20, 30], step=10) == 40


def test_next_number_inserts_into_a_gap():
    assert next_number([10, 20], step=10, after=10) == 15
    assert next_number([10, 15, 20], step=10, after=15) == 17
    assert next_number([10, 20], step=10, after=20) == 30


def test_next_number_refuses_when_there_is_no_gap():
    with pytest.raises(NamingError, match="no free number"):
        next_number([10, 11], step=10, after=10)
    with pytest.raises(NamingError, match="no 12"):
        next_number([10, 20], step=10, after=12)
