"""Tests for webhook processing — deduplication, normalization."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.ingestion.webhook import process_webhook


class TestProcessWebhook:
    async def test_creates_alert(self, session: AsyncSession):
        payload = {
            "rule_name": "Test Rule",
            "severity": "high",
            "source_ip": "10.0.0.1",
        }
        alert = await process_webhook(session, payload, source="webhook")
        assert alert.title == "Test Rule"
        assert alert.severity == "high"
        assert alert.source_ip == "10.0.0.1"
        assert alert.status == "new"

    async def test_deduplication(self, session: AsyncSession):
        payload = {
            "source_id": "dedup-test-100",
            "rule_name": "Dup Rule",
            "severity": "low",
        }
        alert1 = await process_webhook(session, payload, source="webhook")
        alert2 = await process_webhook(session, payload, source="webhook")
        assert alert1.id == alert2.id
        assert alert2.duplicate_count == 2

    async def test_different_source_id_not_deduplicated(self, session: AsyncSession):
        payload1 = {"source_id": "unique-1", "rule_name": "Alert 1", "severity": "low"}
        payload2 = {"source_id": "unique-2", "rule_name": "Alert 2", "severity": "low"}
        alert1 = await process_webhook(session, payload1, source="webhook")
        alert2 = await process_webhook(session, payload2, source="webhook")
        assert alert1.id != alert2.id

    async def test_no_source_id_creates_new(self, session: AsyncSession):
        payload = {"rule_name": "No ID", "severity": "medium"}
        alert1 = await process_webhook(session, payload, source="webhook")
        alert2 = await process_webhook(session, payload, source="webhook")
        assert alert1.id != alert2.id

    async def test_ioc_extraction(self, session: AsyncSession):
        payload = {
            "rule_name": "Malware Detected",
            "severity": "critical",
            "source_ip": "192.168.1.100",
            "file_hash": "abc123def456",
        }
        alert = await process_webhook(session, payload, source="webhook")
        assert alert.iocs is not None
        assert "192.168.1.100" in alert.iocs.get("ips", [])
        assert "abc123def456" in alert.iocs.get("hashes", [])

    async def test_stores_raw_payload(self, session: AsyncSession):
        payload = {"rule_name": "Raw Test", "severity": "low", "custom_field": "custom_value"}
        alert = await process_webhook(session, payload, source="webhook")
        assert alert.raw_payload == payload

    async def test_tags_preserved(self, session: AsyncSession):
        payload = {
            "rule_name": "Tagged Alert",
            "severity": "medium",
            "tags": ["malware", "apt"],
        }
        alert = await process_webhook(session, payload, source="webhook")
        assert alert.tags == ["malware", "apt"]
