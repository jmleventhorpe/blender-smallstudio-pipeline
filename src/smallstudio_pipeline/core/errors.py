"""Errors the pipeline reports to artists. Messages are plain English and say what to do."""


class PipelineError(Exception):
    """Base for every error the tool shows to the artist."""


class NamingError(PipelineError):
    """A name or version doesn't follow the project's naming rules."""
