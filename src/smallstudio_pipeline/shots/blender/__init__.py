"""Shots in Blender: the sequence layout file, and its menu actions."""

import bpy


def register() -> None:
    """Register shots' menu actions."""
    from .operators import CLASSES  # Here, not above: other jobs import modules beside it.

    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    from .operators import CLASSES

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
