from pathlib import Path

from smallstudio_pipeline.project.core.machine import (
    ENV,
    MachineSettings,
    ProjectFolder,
    load_settings,
    save_settings,
    settings_path,
)


def test_settings_round_trip(tmp_path: Path):
    path = tmp_path / "projects.json"
    settings = MachineSettings([ProjectFolder("show", "/mnt/nas/show"), ProjectFolder("b", "")], 0)
    save_settings(settings, path)
    assert load_settings(path) == settings
    assert settings.active_root == Path("/mnt/nas/show")


def test_no_file_means_no_projects(tmp_path: Path):
    settings = load_settings(tmp_path / "missing.json")
    assert settings == MachineSettings() and settings.active_root is None


def test_a_damaged_file_means_no_projects(tmp_path: Path, caplog):
    path = tmp_path / "projects.json"
    path.write_text('{"projects": [{"name": 3}]}')
    assert load_settings(path) == MachineSettings()
    assert "Couldn't read" in caplog.text


def test_an_active_project_out_of_range_or_without_a_folder_is_none():
    assert MachineSettings([ProjectFolder("show", "/s")], active=2).active_root is None
    assert MachineSettings([ProjectFolder("show", "")], active=0).active_root is None


def test_the_environment_can_point_at_another_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(ENV, str(tmp_path / "studio.json"))
    assert settings_path() == tmp_path / "studio.json"


def test_the_default_file_is_outside_blender(monkeypatch, tmp_path: Path):
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr("sys.platform", "linux")
    assert settings_path() == tmp_path / "smallstudio-pipeline" / "projects.json"
