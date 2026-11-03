from pathlib import Path

import pytest

from smallstudio_pipeline.core.project import Project


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project.create(tmp_path / "show")


@pytest.fixture
def make_project(tmp_path: Path):
    """Make a project with extra pipeline.toml settings."""

    def make(settings: str) -> Project:
        root = tmp_path / "custom_show"
        root.mkdir()
        (root / "pipeline.toml").write_text(settings)
        return Project(root)

    return make
