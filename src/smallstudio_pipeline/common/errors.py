"""The errors the pipeline raises, all subclasses of PipelineError.

Each message is written for the artist: what's wrong and what to do. Operators catch
PipelineError and show the message as it is, so anything raised here reaches the artist
word for word.
"""


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
