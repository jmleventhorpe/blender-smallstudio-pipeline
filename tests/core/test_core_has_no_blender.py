"""Each job's core/ and common/ must run in plain Python, so they never import Blender."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).parents[2] / "src" / "smallstudio_pipeline"
NO_BLENDER = [PACKAGE / "common", *PACKAGE.glob("*/core")]
BLENDER_MODULES = {"bpy", "bmesh", "mathutils", "bpy_extras", "gpu"}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_core_modules_do_not_import_blender():
    offenders = {
        str(path.relative_to(PACKAGE)): sorted(imported_modules(path) & BLENDER_MODULES)
        for folder in NO_BLENDER
        for path in folder.rglob("*.py")
        if imported_modules(path) & BLENDER_MODULES
    }
    assert len(NO_BLENDER) == 6, NO_BLENDER  # common and five jobs' core folders.
    assert not offenders, f"core imports Blender modules: {offenders}"
