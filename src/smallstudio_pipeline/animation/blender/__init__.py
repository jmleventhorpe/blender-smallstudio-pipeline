"""Animation in Blender: building a sequence's animation file from its layout publish,
and its menu actions."""

import bpy


def register() -> None:
    """Register animation's menu actions."""
    for cls in _classes():
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_classes()):
        bpy.utils.unregister_class(cls)


def _classes() -> tuple:
    # Imported here, not above: other jobs import modules beside these.
    from . import operators

    return operators.CLASSES
