"""Small Studio Pipeline: publishing, loading and scene construction inside Blender.

The add-on is split by job: project (settings, names and paths, entities), workfiles
(what a file is, new workfiles, versions), loading (linking and keeping publishes
current), publishing (checks, then writing publishes), and shots (the layout file and
its cut). In each, core/ holds the rules and never imports Blender, so it runs and is
tested in plain Python; blender/ does the work in Blender and holds the job's menu
actions. common/ holds small shared helpers, session/ keeps every job in step as files
open and save, and interface/ draws the Pipeline menu.

Blender calls register() when the add-on is enabled and unregister() when it's disabled;
each job registers its own classes and handlers. See docs/architecture.md.
"""


def register() -> None:
    for job in _jobs():
        job.register()


def unregister() -> None:
    for job in reversed(_jobs()):
        job.unregister()


def _jobs() -> tuple:
    """Each job's registration, in order: preferences first, the session's handlers last."""
    # Imported here, so each job's core/ can be used without Blender.
    from . import interface, session
    from .loading import blender as loading
    from .project import blender as project
    from .publishing import blender as publishing
    from .shots import blender as shots
    from .workfiles import blender as workfiles

    return (project, workfiles, loading, publishing, shots, interface, session)
