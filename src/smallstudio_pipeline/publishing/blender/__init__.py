"""Publishing in Blender: writing publishes, the checks' results panel, and Publish."""

import bpy


def register() -> None:
    """Register Publish, Check, the results' Select and Fix, and the Publish panel."""
    for cls in _classes():
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_classes()):
        bpy.utils.unregister_class(cls)


def _classes() -> tuple:
    # Imported here, not above: other jobs import modules beside these.
    from . import operators, panels, results

    return (*operators.CLASSES, *results.CLASSES, *panels.CLASSES)
