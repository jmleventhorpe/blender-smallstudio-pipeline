"""The core must run in plain Python, so it can never import Blender modules."""

import ast
from pathlib import Path

CORE = Path(__file__).parents[2] / "src" / "smallstudio_pipeline" / "core"
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
        path.name: sorted(imported_modules(path) & BLENDER_MODULES)
        for path in CORE.rglob("*.py")
        if imported_modules(path) & BLENDER_MODULES
    }
    assert not offenders, f"core imports Blender modules: {offenders}"
