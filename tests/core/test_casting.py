from smallstudio_pipeline.loading.core.casting import (
    instance_id,
    instance_number,
    next_instance_id,
)


def test_instance_ids_are_the_asset_and_a_number():
    assert instance_id("crate", 3) == "crate_03"
    assert instance_number("crate", "crate_03") == 3
    assert instance_number("crate", "barrel_03") is None
    assert instance_number("crate", "crate_lid") is None


def test_a_new_instance_numbers_after_the_highest():
    assert next_instance_id("crate", []) == "crate_01"
    assert next_instance_id("crate", ["crate_01", "crate_04", "barrel_09"]) == "crate_05"


def test_names_with_underscores_number_on_their_own():
    taken = ["street_lamp_02", "street_01"]
    assert next_instance_id("street_lamp", taken) == "street_lamp_03"
    assert next_instance_id("street", taken) == "street_02"
