"""The Blender layer: operators, menus and panels. Only this package imports bpy."""

import bpy

from . import handlers, operators, state
from .ui import menu, preferences, results

# Registered in this order: each module's CLASSES, then its own register() if it has one.
MODULES = (preferences, operators, results, menu, handlers)


def register() -> None:
    for module in MODULES:
        for cls in getattr(module, "CLASSES", ()):
            bpy.utils.register_class(cls)
        if hasattr(module, "register"):
            module.register()
    # bpy.data can't be read while add-ons register at startup, so look at the file just after.
    bpy.app.timers.register(_first_refresh, first_interval=0.0)


def unregister() -> None:
    if bpy.app.timers.is_registered(_first_refresh):
        bpy.app.timers.unregister(_first_refresh)
    for module in reversed(MODULES):
        if hasattr(module, "unregister"):
            module.unregister()
        for cls in reversed(getattr(module, "CLASSES", ())):
            bpy.utils.unregister_class(cls)


def _first_refresh() -> None:
    state.refresh()
    handlers.claim()
    handlers.after_open()
