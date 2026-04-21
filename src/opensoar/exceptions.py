"""Custom exception types for OpenSOAR core (issue #104).

Defined centrally so broad ``except Exception`` catches can be narrowed to a
small, meaningful set while preserving "never block" semantics at ingest,
enrichment, and plugin-load boundaries.

Each class is intentionally lightweight — callers use them to signal
recoverable failures in a specific subsystem. Programming errors (TypeError,
AttributeError on our own code, NameError) are *not* wrapped here: they
should surface during development rather than be swallowed.
"""
from __future__ import annotations


class OpenSOARError(Exception):
    """Base class for OpenSOAR-raised exceptions."""


class PluginLoadError(OpenSOARError):
    """Raised / caught when an optional plugin fails to load.

    Used by :func:`opensoar.plugins.load_optional_plugins` to distinguish
    recoverable import/entry-point failures from programming errors that
    should bubble out during development.
    """


class EnrichmentCacheError(OpenSOARError):
    """Raised / caught around enrichment-cache interactions.

    Callers treat this as a soft failure — enrichment proceeds without the
    cache rather than blocking alert ingest.
    """


class PlaybookImportError(OpenSOARError):
    """Raised / caught when a playbook module fails to import."""
