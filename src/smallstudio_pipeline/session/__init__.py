"""The session: what file is open, and keeping every job in step as files open and save.

state works out the open file once per load or save. handlers runs on load and save and
calls into each job: in-use markers (workfiles), the asset library, versions seen and
instance IDs (loading), the playblast path and the cut in the sequencer (shots).
"""

import bpy


def register() -> None:
    """Add the load and save handlers, then look at the open file once Blender is ready."""
    from . import handlers  # Here, not above: jobs import modules beside it.

    handlers.register()
    # bpy.data can't be read while add-ons register at startup, so look at the file just after.
    bpy.app.timers.register(_first_refresh, first_interval=0.0)


def unregister() -> None:
    from . import handlers

    if bpy.app.timers.is_registered(_first_refresh):
        bpy.app.timers.unregister(_first_refresh)
    handlers.unregister()


def _first_refresh() -> None:
    from ..project.blender import preferences
    from . import handlers, state

    preferences.load_into_preferences()  # From this machine's settings file.
    state.refresh()
    handlers.claim()
    handlers.after_open()
