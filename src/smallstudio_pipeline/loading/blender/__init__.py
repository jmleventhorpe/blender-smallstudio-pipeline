"""Loading in Blender: linking, updates, instances and editable copies, and their actions."""

import bpy


def register() -> None:
    """Register loading's menu actions and the Loaded panel."""
    for cls in _classes():
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_classes()):
        bpy.utils.unregister_class(cls)


def _classes() -> tuple:
    # Imported here, not above: other jobs import modules beside these.
    from . import operators, panels

    return (*operators.CLASSES, *panels.CLASSES)
