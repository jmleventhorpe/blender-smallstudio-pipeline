"""Build the extension zip into dist/ and validate it with Blender.

    python scripts/build_extension.py

Uses `blender` on PATH, or the executable in $BLENDER.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "smallstudio_pipeline"
DIST = ROOT / "dist"


def run_extension_command(*args: str) -> None:
    blender = os.environ.get("BLENDER", "blender")
    subprocess.run([blender, "--factory-startup", "--command", "extension", *args], check=True)


def main() -> None:
    DIST.mkdir(exist_ok=True)
    for old in DIST.glob("*.zip"):
        old.unlink()
    run_extension_command("build", "--source-dir", str(SOURCE), "--output-dir", str(DIST))
    for package in DIST.glob("*.zip"):
        run_extension_command("validate", str(package))
        print(f"Built and validated {package.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
