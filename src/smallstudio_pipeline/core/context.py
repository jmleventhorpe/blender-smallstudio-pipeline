"""What a file is, worked out from its path: entity, task, version, workfile or publish."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .entities import Project

# (template, entity kind, file kind). Versioned files are tried before hero files.
_FILE_TEMPLATES = [
    (f"{entity}_{kind}", entity, kind)
    for entity in ("asset", "sequence", "shot")
    for kind in ("work", "publish", "hero")
]


@dataclass(frozen=True)
class FileContext:
    entity_kind: str  # "asset", "sequence" or "shot"
    entity: str  # "hero", "010_020", "010_020_0030"
    task: str
    version: int | None  # None for a hero file.
    kind: str  # "work", "publish" or "hero"
    padding: int = 3

    @property
    def is_publish(self) -> bool:
        return self.kind != "work"

    @property
    def label(self) -> str:
        """Short text for the top bar, e.g. 'hero · rigging · v012'."""
        if self.kind == "hero":
            state = "published"
        else:
            version = f"v{self.version:0{self.padding}d}"
            state = version if self.kind == "work" else f"publish {version}"
        return f"{self.entity} · {self.task} · {state}"


def file_context(project: Project, path: Path) -> FileContext | None:
    """Return what a file is, or None if it's outside the project or not a pipeline file."""
    try:
        relative = Path(path).resolve().relative_to(project.root)
    except ValueError:
        return None
    for template, entity_kind, kind in _FILE_TEMPLATES:
        fields = project.templates[template].parse(relative.as_posix())
        if fields is not None:
            version = fields.get("version")
            return FileContext(
                entity_kind=entity_kind,
                entity=str(fields[entity_kind]),
                task=str(fields["task"]),
                version=int(version) if version is not None else None,
                kind=kind,
                padding=project.config.version_padding,
            )
    return None
