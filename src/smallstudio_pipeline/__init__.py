"""Small Studio Pipeline: publishing, loading and scene construction inside Blender.

The add-on has two layers. `core` holds the pipeline's rules (project settings, names
and paths, what exists on disk, what a publish is) and never imports Blender, so it runs
and is tested in plain Python. `blender` sits on top and does the work in Blender: the
Pipeline menu and its operators, publishing, and keeping files in step.

Blender calls register() when the add-on is enabled and unregister() when it's disabled.
See docs/architecture.md for how the modules fit together.
"""


def register() -> None:
    # Imported here so the core can be used without Blender.
    from . import blender

    blender.register()


def unregister() -> None:
    from . import blender

    blender.unregister()
