"""Tests for AI alert anomaly detection.

Heuristics covered:
  * Rolling 7-day count baseline per (partner, rule_name, source_ip) with z-score
    greater than 3 flagged as a ``count_spike`` anomaly.
  * First-time source_ip for a (partner, rule_name) flagged as ``first_seen_ip``.
  * A newly elevated severity for a (partner, rule_name) flagged as
    ``new_severity``.
  * Clean traffic and empty history are no-ops.
  * Listing anomalies via the API is tenant scoped.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from opensoar.ai.anomaly import (
    AnomalySignal,
    compute_anomaly_signals,
    zscore,
)
from opensoar.models.alert import Alert
from opensoar.models.anomaly import Anomaly


def _make_alert(
    *,
    partner: str = "acme-corp",
    rule_name: str = "Brute Force",
    source_ip: str | None = "10.0.0.1",
    severity: str = "medium",
    created_at: datetime | None = None,
) -> Alert:
    """Build a detached ``Alert`` instance for baseline calculations."""
    return Alert(
        id=uuid.uuid4(),
        source="webhook",
        title=rule_name,
        severity=severity,
        status="new",
        raw_payload={},
        normalized={},
        source_ip=source_ip,
        rule_name=rule_name,
        partner=partner,
        created_at=created_at or datetime.now(timezone.utc),
    )


# ── Pure helpers ────────────────────────────────────────────────────────────


class TestZScore:
    def test_zscore_basic(self):
        assert zscore(10, mean=5.0, stdev=2.0) == pytest.approx(2.5)

    def test_zscore_zero_stdev_nonzero_deviation(self):
        # When stdev is 0 but sample deviates, return +inf so downstream
        # filters still fire.
        assert zscore(10, mean=5.0, stdev=0.0) == float("inf")

    def test_zscore_zero_stdev_no_deviation(self):
        # Constant signal equal to its mean → no anomaly.
        assert zscore(5, mean=5.0, stdev=0.0) == 0.0


# ── compute_anomaly_signals ────────────────────────────────────────────────


class TestComputeAnomalySignals:
    def test_empty_history_no_anomalies(self):
        """No history + no current alerts → no signals."""
        signals = compute_anomaly_signals(history=[], current=[])
        assert signals == []

    def test_single_alert_no_history_is_first_seen(self):
        """A brand-new rule/source_ip pair produces a first_seen_ip signal."""
        now = datetime.now(timezone.utc)
        alert = _make_alert(created_at=now)
        signals = compute_anomaly_signals(history=[], current=[alert])
        kinds = {s.kind for s in signals}
        assert "first_seen_ip" in kinds

    def test_repeated_source_ip_not_first_seen(self):
        """If the history already contains this source_ip for the rule/partner,
        no first_seen_ip signal fires."""
        now = datetime.now(timezone.utc)
        history = [
            _make_alert(created_at=now - timedelta(days=i))
            for i in range(1, 4)
        ]
        current = [_make_alert(created_at=now)]
        signals = compute_anomaly_signals(history=history, current=current)
        assert all(s.kind != "first_seen_ip" for s in signals)

    def test_count_spike_flags_when_zscore_gt_3(self):
        """A huge jump in daily count for a (partner, rule, source_ip) trips
        count_spike."""
        now = datetime.now(timezone.utc)
        # Baseline: roughly one alert per day for 7 days.
        history: list[Alert] = []
        for day in range(1, 8):
            history.append(
                _make_alert(created_at=now - timedelta(days=day))
            )
        # Today: 40 alerts — massive spike.
        current = [_make_alert(created_at=now) for _ in range(40)]
        signals = compute_anomaly_signals(history=history, current=current)
        spikes = [s for s in signals if s.kind == "count_spike"]
        assert spikes, "expected a count_spike signal"
        spike = spikes[0]
        assert spike.partner == "acme-corp"
        assert spike.rule_name == "Brute Force"
        assert spike.source_ip == "10.0.0.1"
        assert spike.score > 3.0
        assert spike.details["current_count"] == 40

    def test_count_spike_ignored_when_within_baseline(self):
        """Matching baseline volumes produce no spike."""
        now = datetime.now(timezone.utc)
        history = [
            _make_alert(created_at=now - timedelta(days=day))
            for day in range(1, 8)
        ]
        current = [_make_alert(created_at=now)]
        signals = compute_anomaly_signals(history=history, current=current)
        assert all(s.kind != "count_spike" for s in signals)

    def test_new_severity_level_detected(self):
        """A higher severity than previously observed for a rule/partner fires
        new_severity."""
        now = datetime.now(timezone.utc)
        history = [
            _make_alert(severity="low", created_at=now - timedelta(days=2)),
            _make_alert(severity="medium", created_at=now - timedelta(days=1)),
        ]
        current = [_make_alert(severity="critical", created_at=now)]
        signals = compute_anomaly_signals(history=history, current=current)
        new_sev = [s for s in signals if s.kind == "new_severity"]
        assert new_sev, "expected a new_severity signal"
        assert new_sev[0].details["severity"] == "critical"
        assert new_sev[0].details["previous_max"] == "medium"

    def test_known_severity_not_flagged(self):
        """If the severity was already seen, no signal fires."""
        now = datetime.now(timezone.utc)
        history = [
            _make_alert(severity="high", created_at=now - timedelta(days=2)),
            _make_alert(severity="critical", created_at=now - timedelta(days=1)),
        ]
        current = [_make_alert(severity="high", created_at=now)]
        signals = compute_anomaly_signals(history=history, current=current)
        assert all(s.kind != "new_severity" for s in signals)

    def test_partner_isolation_for_first_seen(self):
        """A source_ip seen for tenant A is still ``first_seen_ip`` for tenant B."""
        now = datetime.now(timezone.utc)
        history = [
            _make_alert(partner="acme-corp", created_at=now - timedelta(days=1)),
        ]
        current = [
            _make_alert(partner="contoso", created_at=now),
        ]
        signals = compute_anomaly_signals(history=history, current=current)
        first_seen = [s for s in signals if s.kind == "first_seen_ip"]
        assert first_seen, "each partner keeps an independent baseline"
        assert first_seen[0].partner == "contoso"

    def test_signals_deduplicate_per_key(self):
        """Repeated alerts for the same key only produce one first_seen_ip."""
        now = datetime.now(timezone.utc)
        current = [_make_alert(created_at=now) for _ in range(3)]
        signals = compute_anomaly_signals(history=[], current=current)
        first_seen = [s for s in signals if s.kind == "first_seen_ip"]
        assert len(first_seen) == 1


class TestAnomalySignalDataclass:
    def test_to_model_payload_round_trips(self):
        sig = AnomalySignal(
            kind="count_spike",
            partner="acme-corp",
            rule_name="Brute Force",
            source_ip="10.0.0.1",
            score=7.5,
            details={"current_count": 40, "baseline_mean": 1.0},
        )
        payload = sig.to_model_payload()
        assert payload["kind"] == "count_spike"
        assert payload["partner"] == "acme-corp"
        assert payload["details"]["current_count"] == 40


# ── Persistence + API endpoint ─────────────────────────────────────────────


class TestAnomalyPersistence:
    async def test_run_detection_persists_anomalies(self, session, db_session_factory):
        """``run_anomaly_detection`` writes Anomaly rows for each signal."""
        from opensoar.ai.anomaly import run_anomaly_detection
        from sqlalchemy import select

        now = datetime.now(timezone.utc)
        unique_partner = f"persist-{uuid.uuid4().hex[:8]}"
        # Seed an alert directly so the detector has something to analyse.
        alert = Alert(
            source="webhook",
            title="Suspicious Login",
            severity="high",
            status="new",
            raw_payload={},
            normalized={},
            source_ip="203.0.113.5",
            rule_name=f"Suspicious Login {uuid.uuid4().hex[:8]}",
            partner=unique_partner,
            created_at=now,
        )
        session.add(alert)
        await session.commit()

        async with db_session_factory() as detect_session:
            created = await run_anomaly_detection(detect_session, now=now)

        assert created >= 1

        rows = (
            await session.execute(
                select(Anomaly).where(Anomaly.partner == unique_partner)
            )
        ).scalars().all()
        assert any(a.kind == "first_seen_ip" for a in rows)
        assert any(a.partner == unique_partner for a in rows)

    async def test_run_detection_is_idempotent(self, session, db_session_factory):
        """Running detection twice on the same data should not duplicate rows."""
        from opensoar.ai.anomaly import run_anomaly_detection
        from sqlalchemy import func, select

        now = datetime.now(timezone.utc)
        unique_partner = f"idem-{uuid.uuid4().hex[:8]}"
        alert = Alert(
            source="webhook",
            title="New Rule",
            severity="medium",
            status="new",
            raw_payload={},
            normalized={},
            source_ip="198.51.100.7",
            rule_name=f"New Rule {uuid.uuid4().hex[:8]}",
            partner=unique_partner,
            created_at=now,
        )
        session.add(alert)
        await session.commit()

        async with db_session_factory() as s1:
            first = await run_anomaly_detection(s1, now=now)
        async with db_session_factory() as s2:
            second = await run_anomaly_detection(s2, now=now)

        assert first >= 1
        assert second == 0, "second pass should not insert duplicate anomalies"

        total = (
            await session.execute(
                select(func.count(Anomaly.id)).where(Anomaly.partner == unique_partner)
            )
        ).scalar() or 0
        assert total == first


class TestAnomalyAPI:
    async def test_list_anomalies_requires_auth(self, client):
        resp = await client.get("/api/v1/ai/anomalies")
        assert resp.status_code == 401

    async def test_list_anomalies_empty_filter(self, client, registered_analyst):
        """Filtering by a partner with no anomalies returns an empty page."""
        unique_partner = f"no-such-partner-{uuid.uuid4().hex[:8]}"
        resp = await client.get(
            f"/api/v1/ai/anomalies?partner={unique_partner}",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"anomalies": [], "total": 0}

    async def test_list_anomalies_returns_recent(
        self, client, registered_analyst, db_session_factory
    ):
        unique_partner = f"partner-{uuid.uuid4().hex[:8]}"
        async with db_session_factory() as sess:
            sess.add(
                Anomaly(
                    kind="count_spike",
                    partner=unique_partner,
                    rule_name="Brute Force",
                    source_ip="10.0.0.1",
                    score=7.1,
                    details={"current_count": 42},
                )
            )
            await sess.commit()

        resp = await client.get(
            f"/api/v1/ai/anomalies?partner={unique_partner}",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["anomalies"][0]["kind"] == "count_spike"
        assert data["anomalies"][0]["partner"] == unique_partner
        assert data["anomalies"][0]["rule_name"] == "Brute Force"

    async def test_list_anomalies_filters(
        self, client, registered_analyst, db_session_factory
    ):
        async with db_session_factory() as sess:
            sess.add(
                Anomaly(
                    kind="count_spike",
                    partner="acme-corp",
                    rule_name="Brute Force",
                    source_ip="10.0.0.1",
                    score=7.1,
                    details={},
                )
            )
            sess.add(
                Anomaly(
                    kind="first_seen_ip",
                    partner="contoso",
                    rule_name="Phish Click",
                    source_ip="198.51.100.7",
                    score=1.0,
                    details={},
                )
            )
            await sess.commit()

        resp = await client.get(
            "/api/v1/ai/anomalies?kind=count_spike",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(a["kind"] == "count_spike" for a in data["anomalies"])

        resp = await client.get(
            "/api/v1/ai/anomalies?partner=contoso",
            headers=registered_analyst["headers"],
        )
        data = resp.json()
        assert all(a["partner"] == "contoso" for a in data["anomalies"])

    async def test_list_anomalies_tenant_isolation(
        self, client, registered_analyst, db_session_factory
    ):
        """Plugin tenant filters must be honoured — rows outside the analyst's
        tenant are excluded when a tenant validator is registered."""
        tenant_a = f"tenant-a-{uuid.uuid4().hex[:8]}"
        tenant_b = f"tenant-b-{uuid.uuid4().hex[:8]}"
        async with db_session_factory() as sess:
            sess.add(
                Anomaly(
                    kind="count_spike",
                    partner=tenant_a,
                    rule_name="Brute Force",
                    source_ip="10.0.0.1",
                    score=7.1,
                    details={},
                )
            )
            sess.add(
                Anomaly(
                    kind="count_spike",
                    partner=tenant_b,
                    rule_name="Brute Force",
                    source_ip="10.0.0.2",
                    score=9.0,
                    details={},
                )
            )
            await sess.commit()

        from opensoar.main import app

        def _only_tenant_a(**kwargs):
            query = kwargs["query"]
            resource_type = kwargs["resource_type"]
            if resource_type != "anomaly":
                return query
            return query.where(Anomaly.partner == tenant_a)

        app.state.tenant_access_validators.append(_only_tenant_a)
        try:
            resp = await client.get(
                "/api/v1/ai/anomalies",
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators.remove(_only_tenant_a)

        assert resp.status_code == 200
        data = resp.json()
        assert all(a["partner"] == tenant_a for a in data["anomalies"])
        # Only one row for tenant_a was inserted by this test.
        assert data["total"] == 1
