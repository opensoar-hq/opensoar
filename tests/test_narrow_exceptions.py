"""Tests for the narrowed exception handlers (issue #104).

These tests lock the new, narrower catch behavior in place so future
regressions that widen them back to ``except Exception`` are caught.

Two complementary assertions per site:
  (a) a *realistic* recoverable exception (ImportError, aiohttp error,
      RedisError, etc.) is still swallowed or logged — the "never block"
      guarantee is preserved.
  (b) a *programming* error (TypeError / AttributeError on our own code,
      ``KeyboardInterrupt``) is no longer silently swallowed and propagates.

These tests intentionally do NOT depend on the ``session`` DB fixture so they
can run without Postgres — making them part of the fast unit suite referenced
in CLAUDE.md.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from opensoar.exceptions import (
    EnrichmentCacheError,
    OpenSOARError,
    PluginLoadError,
)


# ── plugins.load_optional_plugins ─────────────────────────────────────────────


class _FakeEntryPoint:
    def __init__(self, name: str, plugin):
        self.name = name
        self._plugin = plugin

    def load(self):
        return self._plugin


class TestPluginLoaderNarrowCatches:
    def test_import_error_is_caught_and_logged(self, monkeypatch, caplog):
        """A failing plugin import must not crash startup."""
        from opensoar import plugins

        def boom(_app):
            raise ImportError("bad optional dep")

        monkeypatch.setattr(
            plugins,
            "iter_plugin_entry_points",
            lambda group="opensoar.plugins": [_FakeEntryPoint("ee", boom)],
        )

        app = FastAPI()
        with caplog.at_level(logging.ERROR, logger="opensoar.plugins"):
            loaded = plugins.load_optional_plugins(app)

        assert loaded == []
        assert any("Failed to load" in rec.message for rec in caplog.records)

    def test_attribute_error_is_caught_and_logged(self, monkeypatch, caplog):
        """AttributeError during plugin activation is a realistic failure we
        must keep swallowing (e.g. plugin drops an attribute between releases).
        """
        from opensoar import plugins

        def boom(_app):
            raise AttributeError("plugin missing expected attr")

        monkeypatch.setattr(
            plugins,
            "iter_plugin_entry_points",
            lambda group="opensoar.plugins": [_FakeEntryPoint("ee", boom)],
        )

        app = FastAPI()
        with caplog.at_level(logging.ERROR, logger="opensoar.plugins"):
            loaded = plugins.load_optional_plugins(app)

        assert loaded == []
        assert any("Failed to load" in rec.message for rec in caplog.records)

    def test_keyboard_interrupt_propagates(self, monkeypatch):
        """Ctrl-C during plugin activation must not be swallowed — otherwise
        CLI startup becomes unkillable.
        """
        from opensoar import plugins

        def boom(_app):
            raise KeyboardInterrupt

        monkeypatch.setattr(
            plugins,
            "iter_plugin_entry_points",
            lambda group="opensoar.plugins": [_FakeEntryPoint("ee", boom)],
        )

        app = FastAPI()
        with pytest.raises(KeyboardInterrupt):
            plugins.load_optional_plugins(app)


# ── registry._import_module (playbook discovery) ──────────────────────────────


class TestPlaybookRegistryNarrowCatches:
    def test_syntax_error_in_playbook_is_logged_not_raised(
        self, tmp_path, caplog
    ):
        """A broken playbook file must not abort discovery of the others."""
        from opensoar.core.registry import PlaybookRegistry

        bad = tmp_path / "bad.py"
        bad.write_text("def not valid python(\n")

        registry = PlaybookRegistry([str(tmp_path)])
        with caplog.at_level(logging.ERROR, logger="opensoar.core.registry"):
            registry.discover()

        assert any("Failed to import" in rec.message for rec in caplog.records)

    def test_import_error_in_playbook_is_logged_not_raised(
        self, tmp_path, caplog
    ):
        from opensoar.core.registry import PlaybookRegistry

        bad = tmp_path / "bad.py"
        bad.write_text("import a_module_that_does_not_exist_anywhere_xyz\n")

        registry = PlaybookRegistry([str(tmp_path)])
        with caplog.at_level(logging.ERROR, logger="opensoar.core.registry"):
            registry.discover()

        assert any("Failed to import" in rec.message for rec in caplog.records)


# ── enrichment.should_enrich — cache layer ────────────────────────────────────
#
# Use plain mocks rather than the ``session`` fixture so these tests do not
# depend on Postgres being up locally.


def _stub_observable(obs_type: str = "ip", value: str = "9.9.9.9"):
    """A bare object duck-typed as an ``Observable`` for enrichment tests."""
    obs = MagicMock()
    obs.type = obs_type
    obs.value = value
    obs.enrichment_status = "pending"
    obs.enrichments = []
    return obs


class TestShouldEnrichNarrowCatches:
    async def test_redis_error_from_cache_defaults_to_enqueue(self):
        """Redis hiccups while reading the cache must not block enrichment."""
        from opensoar.integrations import cache as cache_mod
        from opensoar.worker import enrichment

        cache_mod.reset_default_cache()

        async def _sources(_session, _obs_type, _partner):
            return ["virustotal"]

        stub_cache = AsyncMock()
        stub_cache.get = AsyncMock(side_effect=ConnectionError("redis down"))

        with (
            patch.object(enrichment, "_configured_sources_for", _sources),
            patch.object(cache_mod, "get_default_cache", return_value=stub_cache),
        ):
            assert (
                await enrichment.should_enrich(MagicMock(), _stub_observable())
                is True
            )

    async def test_type_error_from_cache_lookup_propagates(self):
        """TypeError from our own code during a cache lookup is a bug —
        it should no longer be silently swallowed.
        """
        from opensoar.integrations import cache as cache_mod
        from opensoar.worker import enrichment

        cache_mod.reset_default_cache()

        async def _sources(_session, _obs_type, _partner):
            return ["virustotal"]

        stub_cache = AsyncMock()
        stub_cache.get = AsyncMock(side_effect=TypeError("bad arg"))

        with (
            patch.object(enrichment, "_configured_sources_for", _sources),
            patch.object(cache_mod, "get_default_cache", return_value=stub_cache),
            pytest.raises(TypeError),
        ):
            await enrichment.should_enrich(MagicMock(), _stub_observable())


# ── enqueue_enrichment: broker failure must not block ingest ──────────────────


class TestEnqueueEnrichmentNarrowCatches:
    async def test_broker_connection_error_is_caught(self):
        """ConnectionError from the broker must be caught: enrichment is fire
        and forget and must never propagate into the ingest path.
        """
        from opensoar.integrations import cache as cache_mod
        from opensoar.worker import enrichment

        enrichment.reset_inflight_tracker()
        cache_mod.reset_default_cache()

        obs = _stub_observable(value="7.7.7.7")

        async def _should_enrich(*_args, **_kwargs):
            return True

        with (
            patch.object(enrichment, "should_enrich", _should_enrich),
            patch.object(
                enrichment.enrich_observable_task,
                "delay",
                side_effect=ConnectionError("broker unreachable"),
            ),
        ):
            result = await enrichment.enqueue_enrichment(MagicMock(), obs)
        assert result is False


# ── Exception class public surface ────────────────────────────────────────────


class TestCustomExceptionHierarchy:
    def test_plugin_load_error_inherits_opensoar_error(self):
        assert issubclass(PluginLoadError, OpenSOARError)
        assert issubclass(PluginLoadError, Exception)

    def test_enrichment_cache_error_inherits_opensoar_error(self):
        assert issubclass(EnrichmentCacheError, OpenSOARError)
        assert issubclass(EnrichmentCacheError, Exception)


@pytest.fixture(autouse=True)
def _reset_inflight_and_cache():
    from opensoar.integrations import cache as cache_mod
    from opensoar.worker import enrichment

    enrichment.reset_inflight_tracker()
    cache_mod.reset_default_cache()
    yield
    enrichment.reset_inflight_tracker()
    cache_mod.reset_default_cache()
