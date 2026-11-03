"""The Pipeline menu's operators."""

from .new_asset import PIPELINE_OT_new_asset
from .new_workfile import PIPELINE_OT_new_workfile
from .open import PIPELINE_OT_open
from .publish import PIPELINE_OT_publish
from .version_up import PIPELINE_OT_version_up

CLASSES = (
    PIPELINE_OT_open,
    PIPELINE_OT_new_workfile,
    PIPELINE_OT_new_asset,
    PIPELINE_OT_version_up,
    PIPELINE_OT_publish,
)
