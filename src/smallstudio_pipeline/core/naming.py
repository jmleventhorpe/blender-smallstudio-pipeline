"""Name rules, and the codes for episodes, sequences and shots (010_010_0010)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .errors import NamingError

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
    sequence: str

    def __post_init__(self) -> None:
        if self.episode is not None:
            _number(self.episode, EPISODE_DIGITS, "episode")
        _number(self.sequence, SEQUENCE_DIGITS, "sequence")

    @classmethod
    def parse(cls, text: str, episodes: bool) -> SequenceCode:
        parts = text.split("_")
        if episodes and len(parts) == 2:
            return cls(parts[0], parts[1])
        if not episodes and len(parts) == 1:
            return cls(None, parts[0])
        example = "010_020" if episodes else "020"
        raise NamingError(f"'{text}' isn't a sequence code like {example}.")

    def __str__(self) -> str:
        return self.sequence if self.episode is None else f"{self.episode}_{self.sequence}"


@dataclass(frozen=True, order=True)
class ShotCode:
    """A shot code: '010_020_0030', or '020_0030' without episodes."""

    episode: str | None
    sequence: str
    shot: str

    def __post_init__(self) -> None:
        SequenceCode(self.episode, self.sequence)  # Checks episode and sequence.
        _number(self.shot, SHOT_DIGITS, "shot")

    @classmethod
    def parse(cls, text: str, episodes: bool) -> ShotCode:
        sequence, _, shot = text.rpartition("_")
        try:
            code = SequenceCode.parse(sequence, episodes)
            return cls(code.episode, code.sequence, shot)
        except NamingError:
            example = "010_020_0030" if episodes else "020_0030"
            raise NamingError(f"'{text}' isn't a shot code like {example}.") from None

    @property
    def sequence_code(self) -> SequenceCode:
        return SequenceCode(self.episode, self.sequence)

    def __str__(self) -> str:
        return f"{self.sequence_code}_{self.shot}"


def next_number(existing: Iterable[int], step: int, after: int | None = None) -> int:
    """Return the next code number: a step past the highest, or halfway into a gap.

    With `after`, the new number goes between `after` and the next existing number
    (15 between 10 and 20), so codes can be inserted without renumbering.
    """
    numbers = sorted(set(existing))
    if after is None:
        return (numbers[-1] if numbers else 0) + step
    if after not in numbers:
        raise NamingError(f"There's no {after} to insert after.")
    later = [number for number in numbers if number > after]
    if not later:
        return after + step
    if later[0] - after < 2:
        raise NamingError(f"There's no free number between {after} and {later[0]}.")
    return after + (later[0] - after) // 2
