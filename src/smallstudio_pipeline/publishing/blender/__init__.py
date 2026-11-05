"""Publishing in Blender: writing publishes, the checks' results panel, and Publish."""

import bpy


def register() -> None:
    """Register Publish and the results panel."""
    from .operators import CLASSES  # Here, not above: other jobs import modules beside it.
    from .results import CLASSES as RESULTS

    for cls in (*CLASSES, *RESULTS):
        bpy.utils.register_class(cls)


def unregister() -> None:
    from .operators import CLASSES
    from .results import CLASSES as RESULTS

    for cls in reversed((*CLASSES, *RESULTS)):
        bpy.utils.unregister_class(cls)
