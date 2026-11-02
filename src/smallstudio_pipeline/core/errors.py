"""Errors the pipeline reports to artists. Messages are plain English and say what to do."""


class PipelineError(Exception):
    """Base for every error the tool shows to the artist."""


class ConfigError(PipelineError):
    """The project's pipeline.toml (or the built-in defaults) is invalid."""


class NamingError(PipelineError):
    """A name, code or version doesn't follow the project's naming rules."""


class MetadataError(PipelineError):
    """An entity's metadata file is missing fields or isn't valid JSON."""


class EntityNotFound(PipelineError):
    """An asset, sequence or shot doesn't exist in the project."""


class EntityExists(PipelineError):
    """An asset, sequence or shot with that name or code already exists."""
