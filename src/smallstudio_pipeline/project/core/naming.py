"""Names and codes: the rule for names, and episode, sequence and shot codes.

Codes look like 010_020_0030 (episode, sequence, shot), or 020_0030 in projects without
episodes. SequenceCode and ShotCode parse and print them, and a ShotCode holds its
SequenceCode. next_number() numbers new codes in steps (10, 20…) or halfway into a gap,
so a shot can go between two others (0015 between 0010 and 0020) without renumbering.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ...common.errors import NamingError

DEFAULT_NAME_PATTERN = r"[a-z][a-z0-9_]*"
EPISODE_DIGITS = 3
SEQUENCE_DIGITS = 3
SHOT_DIGITS = 4


def check_name(name: str, pattern: str = DEFAULT_NAME_PATTERN) -> str:
    """Return name if it follows the project's naming rule, else raise NamingError."""
    if not re.fullmatch(pattern, name):
        hint = (
            "Use lowercase letters, digits and underscores, starting with a letter."
            if pattern == DEFAULT_NAME_PATTERN
            else f"Names must match {pattern}."
        )
        raise NamingError(f"'{name}' isn't a valid name. {hint}")
    return name


def _number(text: str, digits: int, what: str) -> str:
    if len(text) != digits or not text.isdigit():
        raise NamingError(f"'{text}' isn't a valid {what} number: use {digits} digits.")
    return text


@dataclass(frozen=True, order=True)
class SequenceCode:
    """A sequence code: '010_020' (episode 010, sequence 020), or '020' without episodes."""

    episode: str | None
    number: str

    def __post_init__(self) -> None:
        if self.episode is not None:
            _number(self.episode, EPISODE_DIGITS, "episode")
        _number(self.number, SEQUENCE_DIGITS, "sequence")

    @classmethod
    def parse(cls, text: str, episodes: bool) -> SequenceCode:
        """Read a sequence code like 010_020 (or 020 without episodes)."""
        parts = text.split("_")
        if episodes and len(parts) == 2:
            return cls(parts[0], parts[1])
        if not episodes and len(parts) == 1:
            return cls(None, parts[0])
        example = "010_020" if episodes else "020"
        raise NamingError(f"'{text}' isn't a sequence code like {example}.")

    def __str__(self) -> str:
        return self.number if self.episode is None else f"{self.episode}_{self.number}"


@dataclass(frozen=True, order=True)
class ShotCode:
    """A shot code: '010_020_0030' (sequence 010_020, shot 0030), or '020_0030'."""

    sequence: SequenceCode
    number: str

    def __post_init__(self) -> None:
        _number(self.number, SHOT_DIGITS, "shot")

    @classmethod
    def parse(cls, text: str, episodes: bool) -> ShotCode:
        """Read a shot code like 010_020_0030 (or 020_0030 without episodes)."""
        sequence, _, number = text.rpartition("_")
        try:
            return cls(SequenceCode.parse(sequence, episodes), number)
        except NamingError:
            example = "010_020_0030" if episodes else "020_0030"
            raise NamingError(f"'{text}' isn't a shot code like {example}.") from None

    def __str__(self) -> str:
        return f"{self.sequence}_{self.number}"


def next_number(existing: Iterable[int], step: int, after: int | None = None) -> int:
    """Return the next code number: a step past the highest, or halfway into a gap.

    With `after`, the new number goes between `after` and the next existing number
    (15 between 10 and 20), so codes can be inserted without renumbering. after=0 puts
    it before the first (5 before 10).
    """
    numbers = sorted(set(existing))
    if after is None:
        return (numbers[-1] if numbers else 0) + step
    if after not in numbers and after != 0:
        raise NamingError(f"There's no {after} to insert after.")
    later = [number for number in numbers if number > after]
    if not later:
        return after + step
    if later[0] - after < 2:
        raise NamingError(f"There's no free number between {after} and {later[0]}.")
    return after + (later[0] - after) // 2
