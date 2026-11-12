"""Instance IDs: which instance of an asset something in a shot is.

Each asset placed in a shot gets an instance ID: the asset's name and a two-digit number
(crate_01, crate_02), kept on whatever stands in the scene. IDs are given once and kept,
so later stages match instances by ID rather than by Blender's names, which gain
suffixes per scene (spike T6). next_instance_id() gives a new instance the number after
the asset's highest in the shot. A shot's casting is the list of its instances
(metadata.CastEntry).
"""

from __future__ import annotations

from collections.abc import Iterable

INSTANCE_DIGITS = 2


def instance_id(asset: str, number: int) -> str:
    """e.g. instance_id("crate", 3) -> "crate_03"."""
    return f"{asset}_{number:0{INSTANCE_DIGITS}d}"


def instance_number(asset: str, text: str) -> int | None:
    """The number in one of the asset's instance IDs ("crate_03" -> 3), or None if it isn't one."""
    name, _, number = text.rpartition("_")
    if name != asset or not number.isdigit():
        return None
    return int(number)


def next_instance_id(asset: str, taken: Iterable[str]) -> str:
    """The ID for a new instance of asset: the number after its highest one in the shot."""
    numbers = [instance_number(asset, text) for text in taken]
    return instance_id(asset, max((n for n in numbers if n is not None), default=0) + 1)
