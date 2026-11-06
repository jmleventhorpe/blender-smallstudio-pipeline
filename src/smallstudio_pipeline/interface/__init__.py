"""The Pipeline menu and top-bar label, the sidebar tab, the dialogs' choices, and more.

menu draws the menu from each job's actions and the label saying what the open file is;
panels holds the Pipeline sidebar tab's shared pieces and its Context panel; browse fills
the Open, New Workfile and New Sequence dialogs; common holds the checks and the
unsaved-changes question the operators share.
"""

import bpy


def register() -> None:
    """Register the Pipeline menu (with the top-bar label) and the Context panel."""
    from . import menu, panels  # Here, not above: jobs import modules beside them.

    menu.register()
    for cls in panels.CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    from . import menu, panels

    for cls in reversed(panels.CLASSES):
        bpy.utils.unregister_class(cls)
    menu.unregister()
