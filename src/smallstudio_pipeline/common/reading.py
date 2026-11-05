"""Reading typed values out of TOML and JSON data, with errors that name the setting.

get() and get_names() check a value's type and say which setting is wrong, e.g.
"tasks.rig.builds_on should be text, not 3". Config, entity metadata and publish
records all read through them, so they report problems the same way. The readers raise
ValueError; config and metadata turn that into their own error types.
"""

from __future__ import annotations

from typing import Any

MISSING = object()
_KIND_NAMES = {
    str: "text",
    int: "a whole number",
    bool: "true or false",
    list: "a list",
    dict: "a table",
}


def get(table: Any, key: str, kind: type, where: str = "", default: Any = MISSING) -> Any:
    """Return table[key], checking its type. A missing value gives `default`, if there is one."""
    name = f"{where}.{key}" if where else key
    if not isinstance(table, dict):
        raise ValueError(f"expected {name} in {table!r}")
    value = table.get(key)
    if value is None:  # Missing, or null in JSON.
        if default is MISSING:
            raise ValueError(f"{name} is missing")
        return default
    # bool is a subclass of int in Python, so rule it out explicitly.
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ValueError(f"{name} should be {_KIND_NAMES[kind]}, not {value!r}")
    return value


def get_names(table: Any, key: str, where: str = "", default: Any = MISSING) -> list[str]:
    """Return table[key] as a list of names (strings)."""
    value = get(table, key, list, where, default)
    if not all(isinstance(item, str) for item in value):
        name = f"{where}.{key}" if where else key
        raise ValueError(f"{name} should be a list of names, not {value!r}")
    return list(value)
