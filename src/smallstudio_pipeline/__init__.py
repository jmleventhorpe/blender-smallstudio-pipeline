"""Small Studio Pipeline: publishing, loading and scene construction inside Blender.

`core` holds the pipeline logic and never imports bpy, so it runs and tests in plain
Python. `blender` is the thin layer of operators, menus and panels on top of it.
"""


def register() -> None:
    # Imported here so the core can be used without Blender.
    from . import blender

    blender.register()


def unregister() -> None:
    from . import blender

    blender.unregister()
