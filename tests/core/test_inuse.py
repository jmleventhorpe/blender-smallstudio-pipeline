import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from smallstudio_pipeline.core import inuse
from smallstudio_pipeline.core.inuse import Marker, claim, marker_path, read_marker, release


@pytest.fixture
def workfile(tmp_path: Path) -> Path:
    path = tmp_path / "hero_rigging_v001.blend"
    path.touch()
    return path


def write_marker(workfile: Path, machine: str, pid: int, age: timedelta = timedelta()) -> None:
    opened = datetime.now(UTC) - age
    data = {"user": "sam", "machine": machine, "pid": pid, "opened": opened.isoformat()}
    marker_path(workfile).write_text(json.dumps(data))


def test_claim_writes_our_marker_and_release_removes_it(workfile):
    assert claim(workfile) is None
    marker = read_marker(workfile)
    assert marker is not None and marker.is_mine()
    assert marker_path(workfile).name == ".hero_rigging_v001.blend.inuse"
    release(workfile)
    assert not marker_path(workfile).exists()


def test_someone_elses_live_marker_is_reported_and_kept(workfile):
    write_marker(workfile, machine="pc-02", pid=4242)
    other = claim(workfile)
    assert other is not None and (other.user, other.machine) == ("sam", "pc-02")
    release(workfile)  # Not ours, so it stays.
    assert read_marker(workfile) == other


def test_old_markers_are_stale(workfile):
    write_marker(workfile, machine="pc-02", pid=4242, age=timedelta(hours=25))
    assert claim(workfile) is None  # Taken over.
    marker = read_marker(workfile)
    assert marker is not None and marker.is_mine()


def test_markers_from_dead_processes_on_this_machine_are_stale(workfile, monkeypatch):
    monkeypatch.setattr(inuse, "_process_running", lambda pid: False)
    marker = Marker("sam", Marker.mine().machine, 999_999, datetime.now(UTC))
    assert marker.is_stale()


def test_markers_from_other_machines_are_trusted_until_old(monkeypatch):
    monkeypatch.setattr(inuse, "_process_running", lambda pid: False)
    marker = Marker("sam", "pc-02", 4242, datetime.now(UTC))
    assert not marker.is_stale()
    assert marker.is_stale(now=datetime.now(UTC) + timedelta(days=2))


def test_a_damaged_marker_is_ignored(workfile):
    marker_path(workfile).write_text("{not json")
    assert read_marker(workfile) is None
    assert claim(workfile) is None
