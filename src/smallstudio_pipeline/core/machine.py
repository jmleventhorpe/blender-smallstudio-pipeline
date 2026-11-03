"""This machine's settings: the project folders it knows, and which one is active.

They're kept in projects.json in a per-user folder outside Blender, so they survive
add-on updates and Blender upgrades: ~/.config/smallstudio-pipeline on Linux,
%APPDATA%\\smallstudio-pipeline on Windows, ~/Library/Application Support/... on macOS.
The SMALLSTUDIO_PIPELINE_SETTINGS environment variable points at a different file (a
studio-wide one, or the tests'). Paths are per machine, so a NAS mounted differently on
Windows and Linux still works.

    {"active": 0, "projects": [{"name": "show", "path": "/mnt/nas/show"}]}
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .files import write_atomic
from .reading import get

log = logging.getLogger(__name__)

ENV = "SMALLSTUDIO_PIPELINE_SETTINGS"
FOLDER = "smallstudio-pipeline"
FILE_NAME = "projects.json"


@dataclass
class ProjectFolder:
    name: str
    path: str  # As this machine sees it.


@dataclass
class MachineSettings:
    projects: list[ProjectFolder] = field(default_factory=list)
    active: int = 0  # Index into projects: the project used when a file isn't in one.

    @property
    def active_root(self) -> Path | None:
        """The active project's folder, or None if there isn't one."""
        if not 0 <= self.active < len(self.projects) or not self.projects[self.active].path:
            return None
        return Path(self.projects[self.active].path).expanduser()


def settings_path() -> Path:
    """Where this machine's settings file is."""
    if os.environ.get(ENV):
        return Path(os.environ[ENV]).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / FOLDER / FILE_NAME


def load_settings(path: Path | None = None) -> MachineSettings:
    """Read this machine's settings. A missing file gives none; a damaged one is logged."""
    path = path or settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        projects = [
            ProjectFolder(get(entry, "name", str), get(entry, "path", str))
            for entry in get(data, "projects", list, default=[])
        ]
        return MachineSettings(projects, get(data, "active", int, default=0))
    except FileNotFoundError:
        return MachineSettings()
    except (OSError, ValueError) as error:
        log.warning("Couldn't read %s, so no projects are set: %s", path, error)
        return MachineSettings()


def save_settings(settings: MachineSettings, path: Path | None = None) -> None:
    """Write this machine's settings."""
    write_atomic(path or settings_path(), json.dumps(asdict(settings), indent=2) + "\n")
