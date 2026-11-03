"""The Pipeline menu's operators, one per file.

Each operator gathers what the artist chose, leaves the rules to the core and the work to
the Blender layer, and turns a PipelineError into a message for the artist.
"""

from .add_shot import PIPELINE_OT_add_shot
from .check_updates import PIPELINE_OT_check_updates
from .make_editable import PIPELINE_OT_make_editable
from .new_asset import PIPELINE_OT_new_asset
from .new_sequence import PIPELINE_OT_new_sequence
from .new_workfile import PIPELINE_OT_new_workfile
from .omit_shot import PIPELINE_OT_omit_shot
from .open import PIPELINE_OT_open
from .override_for_posing import PIPELINE_OT_override_for_posing
from .publish import PIPELINE_OT_publish
from .version_up import PIPELINE_OT_version_up

CLASSES = (
    PIPELINE_OT_open,
    PIPELINE_OT_new_workfile,
    PIPELINE_OT_new_asset,
    PIPELINE_OT_new_sequence,
    PIPELINE_OT_version_up,
    PIPELINE_OT_publish,
    PIPELINE_OT_check_updates,
    PIPELINE_OT_make_editable,
    PIPELINE_OT_override_for_posing,
    PIPELINE_OT_add_shot,
    PIPELINE_OT_omit_shot,
)
