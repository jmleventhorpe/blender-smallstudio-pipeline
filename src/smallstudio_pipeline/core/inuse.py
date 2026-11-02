"""In-use markers: a small file next to an open workfile saying who has it open.

Not a lock. It lets the tool warn when two people open the same file on a shared drive,
for example the one-artist-per-sequence lighting file.
"""

from __future__ import annotations

import getpass
import json
import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .files import write_atomic

# A marker this old is left over from a crash, wherever it came from.
STALE_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class Marker:
    user: str
    machine: str
    pid: int  # The Blender process that opened the file.
    opened: datetime

    @classmethod
    def mine(cls) -> Marker:
        return cls(_user(), socket.gethostname(), os.getpid(), datetime.now(UTC))

    def is_mine(self) -> bool:
        return (self.machine, self.pid) == (socket.gethostname(), os.getpid())

    def is_stale(self, now: datetime | None = None) -> bool:
        """True for a marker left by a crash: too old, or from a process that's gone."""
        if (now or datetime.now(UTC)) - self.opened > STALE_AFTER:
            return True
        # Only processes on this machine can be checked.
        return self.machine == socket.gethostname() and not _process_running(self.pid)


def marker_path(workfile: Path) -> Path:
    return workfile.with_name(f".{workfile.name}.inuse")


def read_marker(workfile: Path) -> Marker | None:
    """Return the file's marker, or None if there isn't a readable one."""
    try:
        data = json.loads(marker_path(workfile).read_text(encoding="utf-8"))
        return Marker(
            data["user"], data["machine"], data["pid"], datetime.fromisoformat(data["opened"])
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None  # Missing or damaged: nobody we can name has the file open.


def claim(workfile: Path) -> Marker | None:
    """Mark the file as open by us. If someone else already has it open, leave their
    marker and return it instead."""
    other = read_marker(workfile)
    if other is not None and not other.is_mine() and not other.is_stale():
        return other
    marker = Marker.mine()
    data = {
        "user": marker.user,
        "machine": marker.machine,
        "pid": marker.pid,
        "opened": marker.opened.isoformat(),
    }
    write_atomic(marker_path(workfile), json.dumps(data, indent=2) + "\n")
    return None


def release(workfile: Path) -> None:
    """Remove the file's marker if it's ours."""
    marker = read_marker(workfile)
    if marker is not None and marker.is_mine():
        marker_path(workfile).unlink(missing_ok=True)


def _user() -> str:
    try:
        return getpass.getuser()
    except OSError:
        return "unknown"


def _process_running(pid: int) -> bool:
    if os.name == "nt":
        # On Windows os.kill(pid, 0) would send Ctrl+C to the process, so ask the system.
        import ctypes

        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # Query limited info.
        if not process:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(process, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(process)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)  # Signal 0 checks the process exists without touching it.
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Exists, but belongs to another user.
    return True
