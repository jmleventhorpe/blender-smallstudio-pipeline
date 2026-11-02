"""The Pipeline menu's operators."""

from .new_asset import PIPELINE_OT_new_asset
from .new_workfile import PIPELINE_OT_new_workfile

CLASSES = (
    PIPELINE_OT_new_asset,
    PIPELINE_OT_new_workfile,
)
