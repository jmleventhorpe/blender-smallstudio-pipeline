"""The Blender layer: operators, menus and panels. Only this package imports bpy."""

import bpy

from . import operators, preferences, state

# Modules whose CLASSES are registered, in order.
MODULES = (preferences, operators)


def register() -> None:
    for module in MODULES:
        for cls in module.CLASSES:
            bpy.utils.register_class(cls)
    # bpy.data can't be read while add-ons register at startup, so look at the file just after.
    bpy.app.timers.register(_first_refresh, first_interval=0.0)


def unregister() -> None:
    if bpy.app.timers.is_registered(_first_refresh):
        bpy.app.timers.unregister(_first_refresh)
    for module in reversed(MODULES):
        for cls in reversed(module.CLASSES):
            bpy.utils.unregister_class(cls)


def _first_refresh() -> None:
    state.refresh()
