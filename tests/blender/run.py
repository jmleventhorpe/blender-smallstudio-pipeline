"""Run the Blender test suite inside headless Blender.

    uv pip install --python 3.13 --target .blender-site pytest src/smallstudio_pipeline/wheels/*.whl
    blender -b --factory-startup --python tests/blender/run.py -- [pytest options]

Blender doesn't bundle pytest or publish-validator, and its own Python may be read-only
(snap, CI), so both live in .blender-site and are put on the path here.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / ".blender-site"), str(ROOT / "src")]

import pytest

options = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
sys.exit(pytest.main([str(ROOT / "tests" / "blender"), "-p", "no:cacheprovider", *options]))
