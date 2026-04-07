"""Tests for webhook ingestion endpoints."""
from __future__ import annotations

from unittest.mock import patch



class TestGenericWebhook:
    async def test_ingest_alert(self, client):
        payload = {
            "rule_name": "SSH Brute Force",
            "severity": "high",
            "source_ip": "203.0.113.42",
            "hostname": "web-prod-01",
            "tags": ["authentication", "brute-force"],
        }
        resp = await client.post("/api/v1/webhooks/alerts", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "SSH Brute Force"
        assert data["severity"] == "high"
        assert data["alert_id"]
        assert "playbooks_triggered" in data

    async def test_ingest_minimal_payload(self, client):
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"message": "Something happened"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Something happened"

    async def test_deduplication(self, client):
        payload = {
            "source_id": f"dedup-test-{__import__('uuid').uuid4().hex[:8]}",
            "rule_name": "Duplicate Alert",
            "severity": "low",
        }
        resp1 = await client.post("/api/v1/webhooks/alerts", json=payload)
        resp2 = await client.post("/api/v1/webhooks/alerts", json=payload)
        assert resp1.json()["alert_id"] == resp2.json()["alert_id"]

    async def test_dispatches_matched_playbooks_as_ordered_sequence(self, client):
        from opensoar.core.decorators import PlaybookMeta, RegisteredPlaybook

        async def pb_first(alert):
            return None

        async def pb_second(alert):
            return None

        ordered_matches = [
            RegisteredPlaybook(
                meta=PlaybookMeta(name="docker_prepare", trigger="webhook", order=10),
                func=pb_first,
                module="test",
            ),
            RegisteredPlaybook(
                meta=PlaybookMeta(name="docker_restart", trigger="webhook", order=20),
                func=pb_second,
                module="test",
            ),
        ]

        fake_engine = type("Engine", (), {"match": lambda self, source, alert_data: ordered_matches})()
        captured = {}

        class FakeTask:
            id = "fake-sequence-task"

        def fake_delay(playbook_names, alert_id):
            captured["playbook_names"] = playbook_names
            captured["alert_id"] = alert_id
            return FakeTask()

        with patch("opensoar.main.get_trigger_engine", return_value=fake_engine):
            with patch("opensoar.worker.tasks.execute_playbook_sequence_task.delay", side_effect=fake_delay):
                resp = await client.post(
                    "/api/v1/webhooks/alerts",
                    json={"rule_name": "Docker Alert", "severity": "high", "tags": ["Docker"]},
                )

        assert resp.status_code == 200
        assert captured["playbook_names"] == ["docker_prepare", "docker_restart"]
        assert resp.json()["playbooks_triggered"] == ["docker_prepare", "docker_restart"]


class TestElasticWebhook:
    async def test_ingest_elastic_alert(self, client):
        payload = {
            "rule": {
                "name": "Elastic Detection Rule",
                "severity": "critical",
            },
            "source": {"ip": "172.16.0.1"},
            "host": {"name": "elastic-node-01"},
            "_id": f"elastic-{__import__('uuid').uuid4().hex[:8]}",
        }
        resp = await client.post("/api/v1/webhooks/alerts/elastic", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Elastic Detection Rule"
        assert data["severity"] == "critical"
