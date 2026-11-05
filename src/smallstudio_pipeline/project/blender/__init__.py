"""The project in Blender: which asset a root collection is, and the preferences page."""

import bpy


def register() -> None:
    """Register the preferences page."""
    from .preferences import CLASSES  # Here, not above: other jobs import modules beside it.

    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    from .preferences import CLASSES

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
