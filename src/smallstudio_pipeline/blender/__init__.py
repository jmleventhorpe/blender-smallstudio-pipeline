"""The Blender layer: operators, menus and panels. Only this package imports bpy."""

import bpy

# Operator, menu and panel classes, in registration order.
CLASSES: tuple[type, ...] = ()


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
