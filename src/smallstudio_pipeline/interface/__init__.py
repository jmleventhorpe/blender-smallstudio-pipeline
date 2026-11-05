"""The Pipeline menu and top-bar label, the dialogs' choices, and what operators share.

menu draws the menu from each job's actions and the label saying what the open file is;
browse fills the Open, New Workfile and New Sequence dialogs; common holds the checks
and the unsaved-changes question the operators share.
"""


def register() -> None:
    """Register the Pipeline menu and add it, with the label, to the top bar."""
    from . import menu  # Here, not above: jobs import modules beside it.

    menu.register()


def unregister() -> None:
    from . import menu

    menu.unregister()
