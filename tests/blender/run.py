"""Run the Blender test suite inside headless Blender.

    uv pip install --python 3.13 --target .blender-site pytest
    blender -b --factory-startup --python tests/blender/run.py -- [pytest options]

Blender doesn't bundle pytest, and its own Python may be read-only (snap, CI), so pytest
lives in .blender-site and is put on the path here.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / ".blender-site"), str(ROOT / "src")]

import pytest

options = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
sys.exit(pytest.main([str(ROOT / "tests" / "blender"), "-p", "no:cacheprovider", *options]))
