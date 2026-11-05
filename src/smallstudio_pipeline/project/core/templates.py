"""Path templates: named patterns that turn fields into paths, and paths back into fields.

The patterns come from the config's [templates] tables, so a project can change its
folder layout without changing code. Each field must match a pattern built from the
config (asset types, task names, the name rule, code shapes), so names and paths can't
drift apart. Project.path() and Project.find_files() are the usual way in.

    asset_work = "assets/{asset_type}/{asset}/{task}/work/{asset}_{task}_v{version}.blend"

    format(asset_type="character", asset="hero", task="rig", version=12)
        -> assets/character/hero/rig/work/hero_rig_v012.blend
    parse("assets/character/hero/rig/work/hero_rig_v012.blend")
        -> {"asset_type": "character", "asset": "hero", "task": "rig", "version": 12}
"""

from __future__ import annotations

import re
from pathlib import Path, PurePath, PurePosixPath

from ...common.errors import ConfigError, NamingError
from .config import Config
from .naming import EPISODE_DIGITS, SEQUENCE_DIGITS, SHOT_DIGITS

# {field}, or {@other_template} to include another template.
_PLACEHOLDER = re.compile(r"\{(@?)([a-z_]+)\}")

Fields = dict[str, str | int]


class Template:
    """A path pattern relative to the project root, or to the render root if `render`."""

    def __init__(
        self, name: str, pattern: str, patterns: dict[str, str], padding: int, render: bool = False
    ):
        self.name = name
        self.pattern = pattern
        self.render = render
        self._patterns = patterns  # Field name -> the regex its values must match.
        self._padding = padding
        # The template's field names, in order, each once.
        self.fields = tuple(
            dict.fromkeys(match.group(2) for match in _PLACEHOLDER.finditer(pattern))
        )
        for field in self.fields:
            if field not in patterns:
                known = ", ".join(f"{{{name}}}" for name in patterns)
                raise ConfigError(f"Template {name} uses {{{field}}}; fields are {known}.")
        self._regex = re.compile(self._build_regex())

    def __repr__(self) -> str:
        return f"Template({self.name!r}, {self.pattern!r})"

    def format(self, **values: str | int) -> PurePosixPath:
        """Return the path for these field values, or raise NamingError."""
        return PurePosixPath(self._fill(values))

    def parse(self, path: str | PurePath) -> Fields | None:
        """Return the fields in a path relative to the template root, or None if it won't fit."""
        match = self._regex.fullmatch(str(path).replace("\\", "/"))
        if match is None:
            return None
        fields: Fields = dict(match.groupdict())
        if "version" in fields:
            fields["version"] = int(fields["version"])
        return fields

    def find(self, root: Path, **known: str | int) -> list[tuple[Path, Fields]]:
        """Return the existing paths under root that fit, with their fields.

        Fields given in `known` are fixed; the rest can be anything.
        """
        found = []
        for path in sorted(root.glob(self._fill(known, wildcard=True))):
            fields = self.parse(path.relative_to(root).as_posix())
            if fields is not None:
                found.append((path, fields))
        return found

    def _fill(self, values: dict[str, str | int], wildcard: bool = False) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(2)
            if key in values:
                return self._text(key, values[key])
            if wildcard:
                return "*"
            raise NamingError(f"The {self.name} path needs a {key.replace('_', ' ')}.")

        return _PLACEHOLDER.sub(replace, self.pattern)

    def _text(self, key: str, value: str | int) -> str:
        if key == "version" and isinstance(value, int):
            text = f"{value:0{self._padding}d}"
        else:
            text = str(value)
        if not re.fullmatch(self._patterns[key], text):
            raise NamingError(f"'{text}' isn't a valid {key.replace('_', ' ')}.")
        return text

    def _build_regex(self) -> str:
        parts, seen, position = [], set(), 0
        for match in _PLACEHOLDER.finditer(self.pattern):
            parts.append(re.escape(self.pattern[position : match.start()]))
            key = match.group(2)
            # A field used twice must have the same value both times (asset folder and file).
            parts.append(f"(?P={key})" if key in seen else f"(?P<{key}>{self._patterns[key]})")
            seen.add(key)
            position = match.end()
        parts.append(re.escape(self.pattern[position:]))
        return "".join(parts)


def _field_patterns(config: Config) -> dict[str, str]:
    """Return the regex each template field must match, from the project's config."""

    def one_of(names: list[str]) -> str:
        # Longest first, so 'set' can't match the start of 'set_dressing'.
        return "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))

    sequence = rf"\d{{{SEQUENCE_DIGITS}}}"
    if config.episodes:
        sequence = rf"\d{{{EPISODE_DIGITS}}}_{sequence}"
    return {
        "asset_type": one_of(list(config.asset_types)),
        "asset": config.name_pattern,
        "task": one_of(list(config.tasks)),
        "version": r"\d+",
        "episode": rf"\d{{{EPISODE_DIGITS}}}",
        "sequence": sequence,
        "shot": rf"{sequence}_\d{{{SHOT_DIGITS}}}",
    }


def build_templates(config: Config) -> dict[str, Template]:
    """Build every template in the config, with {@includes} expanded."""
    templates = {**config.templates, **config.render_templates}
    patterns = _field_patterns(config)
    return {
        name: Template(
            name,
            _expand(name, templates),
            patterns,
            config.version_padding,
            render=name in config.render_templates,
        )
        for name in templates
    }


def _expand(name: str, patterns: dict[str, str], chain: tuple[str, ...] = ()) -> str:
    if name in chain:
        raise ConfigError(f"Template {name} includes itself: {' -> '.join((*chain, name))}.")

    def replace(match: re.Match[str]) -> str:
        if not match.group(1):
            return match.group(0)
        include = match.group(2)
        if include not in patterns:
            raise ConfigError(f"Template {name} includes {{@{include}}}, which doesn't exist.")
        return _expand(include, patterns, (*chain, name))

    return _PLACEHOLDER.sub(replace, patterns[name])
