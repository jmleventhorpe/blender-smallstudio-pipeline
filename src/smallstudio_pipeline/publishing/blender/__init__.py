"""Publishing in Blender: writing publishes, the checks' results panel, and Publish."""

import bpy


def register() -> None:
    """Register Publish, Check, the results' Select and Fix, the Publish panel, and its
    Link Back option (kept on the window manager, for this session)."""
    for cls in _classes():
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.pipeline_link_back = bpy.props.BoolProperty(  # pyright: ignore[reportAttributeAccessIssue]
        name="Link Back",
        description="After publishing, swap the node for a link to its new publish, in place",
    )


def unregister() -> None:
    del bpy.types.WindowManager.pipeline_link_back  # pyright: ignore[reportAttributeAccessIssue]
    for cls in reversed(_classes()):
        bpy.utils.unregister_class(cls)


def _classes() -> tuple:
    # Imported here, not above: other jobs import modules beside these.
    from . import operators, panels, results

    return (*operators.CLASSES, *results.CLASSES, *panels.CLASSES)
