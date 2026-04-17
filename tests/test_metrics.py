"""Tests for the Prometheus /metrics endpoint and metric recording helpers."""
from __future__ import annotations

import pytest

from opensoar.middleware import metrics as metrics_mod


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Clear all samples between tests so counters/histograms start at zero."""
    metrics_mod.reset_metrics()
    yield
    metrics_mod.reset_metrics()


class TestMetricsRegistry:
    def test_registry_exposes_expected_metric_names(self):
        text = metrics_mod.render_metrics().decode("utf-8")
        for name in (
            "opensoar_http_requests_total",
            "opensoar_alerts_ingested_total",
            "opensoar_playbook_runs_total",
            "opensoar_playbook_run_duration_seconds",
        ):
            assert name in text, f"metric {name} should appear in exposition text"

    def test_content_type_is_prometheus_text_format(self):
        content_type = metrics_mod.metrics_content_type()
        assert content_type.startswith("text/plain")
        assert "version=" in content_type

    def test_record_alert_ingested_increments_counter(self):
        metrics_mod.record_alert_ingested("webhook")
        metrics_mod.record_alert_ingested("webhook")
        metrics_mod.record_alert_ingested("elastic")

        text = metrics_mod.render_metrics().decode("utf-8")
        assert 'opensoar_alerts_ingested_total{source="webhook"} 2.0' in text
        assert 'opensoar_alerts_ingested_total{source="elastic"} 1.0' in text

    def test_record_playbook_run_increments_counter_and_histogram(self):
        metrics_mod.record_playbook_run("triage", "success", 0.25)
        metrics_mod.record_playbook_run("triage", "failed", 1.5)

        text = metrics_mod.render_metrics().decode("utf-8")
        assert (
            'opensoar_playbook_runs_total{playbook="triage",status="success"} 1.0'
            in text
        )
        assert (
            'opensoar_playbook_runs_total{playbook="triage",status="failed"} 1.0'
            in text
        )
        # Histogram exposes _count and _sum series
        assert "opensoar_playbook_run_duration_seconds_count" in text
        assert "opensoar_playbook_run_duration_seconds_sum" in text


class TestMetricsEndpoint:
    async def test_metrics_endpoint_returns_200(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")

    async def test_http_requests_counter_increments(self, client):
        # Hit an endpoint first so there is traffic to observe
        await client.get("/api/v1/health")
        await client.get("/api/v1/health")

        resp = await client.get("/metrics")
        body = resp.text
        assert "opensoar_http_requests_total" in body
        # The /metrics endpoint itself is excluded, but /api/v1/health is recorded
        assert 'path="/api/v1/health"' in body
        assert 'method="GET"' in body
        assert 'status="200"' in body

    async def test_metrics_path_excluded_from_counter(self, client):
        await client.get("/metrics")
        await client.get("/metrics")
        resp = await client.get("/metrics")
        assert 'path="/metrics"' not in resp.text

    async def test_alert_ingest_increments_alerts_counter(self, client):
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Metrics Test Alert", "severity": "low"},
        )
        assert resp.status_code == 200

        metrics_resp = await client.get("/metrics")
        body = metrics_resp.text
        assert 'opensoar_alerts_ingested_total{source="webhook"}' in body


class TestPlaybookExecutorMetrics:
    async def test_executor_records_run_metric(self, session):
        """PlaybookExecutor.execute should observe a run in the histogram and counter."""
        from opensoar.core.decorators import PlaybookMeta, RegisteredPlaybook
        from opensoar.core.executor import PlaybookExecutor
        from opensoar.models.playbook import PlaybookDefinition

        # Register a dummy playbook definition in the DB
        pb_row = PlaybookDefinition(
            name="metrics-test-playbook",
            description="pb for metrics",
            module_path="tests.test_metrics",
            function_name="dummy_playbook",
            trigger_type="manual",
            trigger_config={},
            enabled=True,
        )
        session.add(pb_row)
        await session.commit()

        async def dummy(_input):
            return {"ok": True}

        pb = RegisteredPlaybook(
            meta=PlaybookMeta(
                name="metrics-test-playbook",
                description="pb for metrics",
                trigger="manual",
                conditions={},
            ),
            func=dummy,
            module="tests.test_metrics",
        )

        executor = PlaybookExecutor(session)
        run = await executor.execute(pb)
        assert run.status == "success"

        text = metrics_mod.render_metrics().decode("utf-8")
        assert (
            'opensoar_playbook_runs_total{playbook="metrics-test-playbook",status="success"} 1.0'
            in text
        )
        assert "opensoar_playbook_run_duration_seconds_count" in text
