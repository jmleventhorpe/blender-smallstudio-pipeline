"""Workfiles in Blender: starting and saving them, and their menu actions."""

import bpy


def register() -> None:
    """Register workfiles' menu actions and the Workfiles panel."""
    from . import panels  # Here, not above: other jobs import modules beside these.

    for cls in _classes():
        bpy.utils.register_class(cls)
    panels.register()


def unregister() -> None:
    from . import panels

    panels.unregister()
    for cls in reversed(_classes()):
        bpy.utils.unregister_class(cls)


def _classes() -> tuple:
    from . import operators, panels

    return (*operators.CLASSES, *panels.CLASSES)
