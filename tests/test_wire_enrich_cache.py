"""Tests for wiring auto-enrichment to the TTL cache (issue #89).

``should_enrich`` must consult :class:`EnrichmentCache`: it returns ``False``
only when every configured enrichment source for the observable's type has a
fresh cache entry. Any stale or missing source means the observable still
needs to be enqueued. Cache-driven skips increment the Prometheus counter
``opensoar_enrichment_cache_skips_total{type}``.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.integrations.cache import EnrichmentCache, InMemoryCacheBackend
from opensoar.middleware import metrics as metrics_mod
from opensoar.models.integration import IntegrationInstance
from opensoar.models.observable import Observable


@pytest.fixture(autouse=True)
async def _reset_state(db_session_factory):
    """Reset cache singleton, metrics, in-flight tracker, and any leftover
    integration rows so cases are isolated from the shared test DB.
    """
    from sqlalchemy import delete

    from opensoar.integrations import cache as cache_mod
    from opensoar.worker import enrichment

    async with db_session_factory() as s:
        await s.execute(delete(IntegrationInstance))
        await s.commit()

    cache_mod.reset_default_cache()
    metrics_mod.reset_metrics()
    enrichment.reset_inflight_tracker()
    yield
    async with db_session_factory() as s:
        await s.execute(delete(IntegrationInstance))
        await s.commit()
    cache_mod.reset_default_cache()
    metrics_mod.reset_metrics()
    enrichment.reset_inflight_tracker()


async def _make_cache(monkeypatch) -> EnrichmentCache:
    """Install an isolated in-memory cache as the module-level singleton."""
    from opensoar.integrations import cache as cache_mod

    backend = InMemoryCacheBackend()
    cache = EnrichmentCache(backend=backend)
    monkeypatch.setattr(cache_mod, "get_default_cache", lambda: cache)
    return cache


async def _add_integration(
    session: AsyncSession, integration_type: str, partner: str | None = None
) -> IntegrationInstance:
    instance = IntegrationInstance(
        integration_type=integration_type,
        name=f"{integration_type}-test",
        partner=partner,
        config={"api_key": "test"},
        enabled=True,
    )
    session.add(instance)
    await session.commit()
    await session.refresh(instance)
    return instance


class TestShouldEnrichConsultsCache:
    async def test_no_configured_sources_means_enqueue(
        self, session: AsyncSession, monkeypatch
    ):
        """With no enabled integrations, there is nothing to cache-skip — enqueue."""
        from opensoar.worker import enrichment

        await _make_cache(monkeypatch)
        obs = Observable(type="ip", value="203.0.113.1", source="test")
        assert await enrichment.should_enrich(session, obs, partner=None) is True

    async def test_fresh_cache_for_all_sources_skips(
        self, session: AsyncSession, monkeypatch
    ):
        """If every configured source has a fresh cache entry, skip the enqueue."""
        from opensoar.worker import enrichment

        cache = await _make_cache(monkeypatch)
        await _add_integration(session, "virustotal")
        await _add_integration(session, "abuseipdb")

        value = "203.0.113.2"
        await cache.set("virustotal", "ip", value, {"vt": 1}, ttl_seconds=3600)
        await cache.set("abuseipdb", "ip", value, {"abuse": 1}, ttl_seconds=3600)

        obs = Observable(type="ip", value=value, source="test")
        assert await enrichment.should_enrich(session, obs, partner=None) is False

    async def test_partial_freshness_still_enqueues(
        self, session: AsyncSession, monkeypatch
    ):
        """If any configured source is missing from cache, enqueue."""
        from opensoar.worker import enrichment

        cache = await _make_cache(monkeypatch)
        await _add_integration(session, "virustotal")
        await _add_integration(session, "abuseipdb")

        value = "203.0.113.3"
        # Only VT cached — AbuseIPDB missing => partial freshness.
        await cache.set("virustotal", "ip", value, {"vt": 1}, ttl_seconds=3600)

        obs = Observable(type="ip", value=value, source="test")
        assert await enrichment.should_enrich(session, obs, partner=None) is True

    async def test_expired_entry_enqueues(
        self, session: AsyncSession, monkeypatch
    ):
        """An expired cache entry must be treated as missing and enqueue."""
        from opensoar.worker import enrichment

        cache = await _make_cache(monkeypatch)
        await _add_integration(session, "virustotal")

        value = "203.0.113.4"
        # Force an immediately-expired entry.
        await cache.set("virustotal", "ip", value, {"vt": 1}, ttl_seconds=0)
        cache.backend._fast_forward(1)

        obs = Observable(type="ip", value=value, source="test")
        assert await enrichment.should_enrich(session, obs, partner=None) is True

    async def test_missing_entry_enqueues(
        self, session: AsyncSession, monkeypatch
    ):
        """No cache entries at all must enqueue."""
        from opensoar.worker import enrichment

        await _make_cache(monkeypatch)
        await _add_integration(session, "virustotal")

        obs = Observable(type="ip", value="203.0.113.5", source="test")
        assert await enrichment.should_enrich(session, obs, partner=None) is True

    async def test_type_scoping_ignores_sources_that_dont_handle_type(
        self, session: AsyncSession, monkeypatch
    ):
        """AbuseIPDB only handles IPs — for a hash observable it must not be
        required to have a fresh entry before skipping.
        """
        from opensoar.worker import enrichment

        cache = await _make_cache(monkeypatch)
        await _add_integration(session, "virustotal")
        await _add_integration(session, "abuseipdb")

        value = "d41d8cd98f00b204e9800998ecf8427e"
        # VT handles hashes; AbuseIPDB does not. Only VT fresh => skip.
        await cache.set("virustotal", "hash", value, {"vt": 1}, ttl_seconds=3600)

        obs = Observable(type="hash", value=value, source="test")
        assert await enrichment.should_enrich(session, obs, partner=None) is False

    async def test_partner_scoping_honours_tenant(
        self, session: AsyncSession, monkeypatch
    ):
        """Only integrations matching the observable's partner (or tenant-agnostic)
        contribute to the freshness decision.
        """
        from opensoar.worker import enrichment

        await _make_cache(monkeypatch)
        # Another tenant's VT — must be ignored.
        await _add_integration(session, "virustotal", partner="other-tenant")

        value = "203.0.113.6"
        obs = Observable(type="ip", value=value, source="test")
        # No integrations are configured for this tenant, so there is nothing
        # to cache-skip: enqueue.
        assert await enrichment.should_enrich(session, obs, partner="acme") is True


class TestEnqueueRespectsCache:
    async def test_enqueue_skipped_when_cache_fresh(
        self, session: AsyncSession, monkeypatch
    ):
        """When should_enrich declines, enqueue_enrichment must not call .delay()."""
        from opensoar.worker import enrichment

        cache = await _make_cache(monkeypatch)
        await _add_integration(session, "virustotal")
        await _add_integration(session, "abuseipdb")

        value = "203.0.113.10"
        await cache.set("virustotal", "ip", value, {"vt": 1}, ttl_seconds=3600)
        await cache.set("abuseipdb", "ip", value, {"abuse": 1}, ttl_seconds=3600)

        obs = Observable(type="ip", value=value, source="test")

        with patch(
            "opensoar.worker.enrichment.enrich_observable_task.delay"
        ) as delay:
            enqueued = await enrichment.enqueue_enrichment(
                session, obs, partner=None
            )
            assert enqueued is False
            delay.assert_not_called()

    async def test_enqueue_proceeds_when_cache_stale(
        self, session: AsyncSession, monkeypatch
    ):
        from opensoar.worker import enrichment

        await _make_cache(monkeypatch)
        await _add_integration(session, "virustotal")

        obs = Observable(type="ip", value="203.0.113.11", source="test")

        with patch(
            "opensoar.worker.enrichment.enrich_observable_task.delay"
        ) as delay:
            enqueued = await enrichment.enqueue_enrichment(
                session, obs, partner=None
            )
            assert enqueued is True
            delay.assert_called_once()


class TestCacheSkipMetric:
    async def test_skip_increments_counter_with_type_label(
        self, session: AsyncSession, monkeypatch
    ):
        """A cache-driven skip must bump opensoar_enrichment_cache_skips_total{type}."""
        from opensoar.worker import enrichment

        cache = await _make_cache(monkeypatch)
        await _add_integration(session, "virustotal")

        value = "203.0.113.20"
        await cache.set("virustotal", "ip", value, {"vt": 1}, ttl_seconds=3600)

        obs = Observable(type="ip", value=value, source="test")
        with patch(
            "opensoar.worker.enrichment.enrich_observable_task.delay"
        ):
            await enrichment.enqueue_enrichment(session, obs, partner=None)

        text = metrics_mod.render_metrics().decode("utf-8")
        assert "opensoar_enrichment_cache_skips_total" in text
        assert 'opensoar_enrichment_cache_skips_total{type="ip"} 1.0' in text

    async def test_enqueue_does_not_increment_skip_counter(
        self, session: AsyncSession, monkeypatch
    ):
        """When enqueue proceeds, the skip counter must not tick."""
        from opensoar.worker import enrichment

        await _make_cache(monkeypatch)
        await _add_integration(session, "virustotal")

        obs = Observable(type="ip", value="203.0.113.21", source="test")
        with patch(
            "opensoar.worker.enrichment.enrich_observable_task.delay"
        ):
            await enrichment.enqueue_enrichment(session, obs, partner=None)

        text = metrics_mod.render_metrics().decode("utf-8")
        # Counter may be rendered with 0.0 or not at all depending on whether
        # it has been exercised; either way, no ip=1.0 tick should appear.
        assert 'opensoar_enrichment_cache_skips_total{type="ip"} 1.0' not in text


class TestMetricsHelperExposed:
    def test_record_enrichment_cache_skip_increments_counter(self):
        """The helper function must be wired up against the OpenSOAR registry."""
        metrics_mod.record_enrichment_cache_skip("ip")
        metrics_mod.record_enrichment_cache_skip("ip")
        metrics_mod.record_enrichment_cache_skip("domain")

        text = metrics_mod.render_metrics().decode("utf-8")
        assert 'opensoar_enrichment_cache_skips_total{type="ip"} 2.0' in text
        assert 'opensoar_enrichment_cache_skips_total{type="domain"} 1.0' in text
