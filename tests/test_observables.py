"""Tests for observable tracking and enrichment."""
from __future__ import annotations

from fastapi import HTTPException

from opensoar.plugins import register_tenant_access_validator

class TestObservablesCRUD:
    async def test_create_observable(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/observables",
            json={
                "type": "ip",
                "value": "203.0.113.42",
                "source": "alert-extraction",
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "ip"
        assert data["value"] == "203.0.113.42"
        assert data["enrichment_status"] == "pending"

    async def test_list_observables(self, client, registered_analyst):
        await client.post(
            "/api/v1/observables",
            json={"type": "domain", "value": "evil.example.com", "source": "manual"},
            headers=registered_analyst["headers"],
        )

        resp = await client.get("/api/v1/observables")
        assert resp.status_code == 200
        data = resp.json()
        assert "observables" in data
        assert data["total"] >= 1

    async def test_filter_by_type(self, client, registered_analyst):
        await client.post(
            "/api/v1/observables",
            json={"type": "hash", "value": "abc123def456", "source": "alert"},
            headers=registered_analyst["headers"],
        )

        resp = await client.get("/api/v1/observables?type=hash")
        assert resp.status_code == 200
        for obs in resp.json()["observables"]:
            assert obs["type"] == "hash"

    async def test_add_enrichment(self, client, registered_analyst):
        resp = await client.post(
            "/api/v1/observables",
            json={"type": "ip", "value": "198.51.100.1", "source": "test"},
            headers=registered_analyst["headers"],
        )
        obs_id = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/observables/{obs_id}/enrichments",
            json={
                "source": "virustotal",
                "data": {"malicious": 5, "total": 70},
                "malicious": True,
                "score": 7.1,
            },
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200

        # Check observable now has enrichment
        resp = await client.get(f"/api/v1/observables/{obs_id}")
        data = resp.json()
        assert data["enrichment_status"] == "enriched"
        assert len(data["enrichments"]) >= 1

    async def test_dedup_observable(self, client, registered_analyst):
        """Creating the same observable twice should not duplicate it."""
        body = {"type": "ip", "value": "10.99.99.99", "source": "dedup-test"}
        resp1 = await client.post(
            "/api/v1/observables", json=body, headers=registered_analyst["headers"]
        )
        resp2 = await client.post(
            "/api/v1/observables", json=body, headers=registered_analyst["headers"]
        )
        assert resp1.json()["id"] == resp2.json()["id"]


class TestCorrelationEngine:
    async def test_auto_correlate_by_source_ip(self, client, registered_analyst):
        """Alerts with the same source IP should be suggested for correlation."""
        # Create two alerts with the same source IP
        for i in range(2):
            await client.post(
                "/api/v1/webhooks/alerts",
                json={
                    "rule_name": f"Correlated Alert {i}",
                    "severity": "high",
                    "source_ip": "192.168.99.99",
                },
            )

        resp = await client.get(
            "/api/v1/incidents/suggestions",
            headers=registered_analyst["headers"],
        )
        assert resp.status_code == 200
        suggestions = resp.json()
        assert isinstance(suggestions, list)


class TestObservableTenantHooks:
    async def test_tenant_validator_filters_observable_list(self, client, registered_analyst):
        from opensoar.main import app
        from opensoar.models.observable import Observable

        await client.post(
            "/api/v1/observables",
            json={"type": "ip", "value": "203.0.113.42", "source": "tenant-test"},
            headers=registered_analyst["headers"],
        )
        await client.post(
            "/api/v1/observables",
            json={"type": "ip", "value": "198.51.100.1", "source": "tenant-test"},
            headers=registered_analyst["headers"],
        )

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs["resource_type"] == "observable":
                return query.where(Observable.value == "203.0.113.42")
            return None

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            resp = await client.get("/api/v1/observables", headers=registered_analyst["headers"])
        finally:
            app.state.tenant_access_validators = original_validators

        assert resp.status_code == 200
        assert {obs["value"] for obs in resp.json()["observables"]} == {"203.0.113.42"}

    async def test_tenant_validator_blocks_observable_detail_and_enrichment(self, client, registered_analyst):
        from opensoar.main import app

        create = await client.post(
            "/api/v1/observables",
            json={"type": "ip", "value": "198.51.100.77", "source": "block-test"},
            headers=registered_analyst["headers"],
        )
        obs_id = create.json()["id"]

        async def validator(**kwargs):
            resource = kwargs.get("resource")
            if resource is not None and getattr(resource, "value", None) == "198.51.100.77":
                raise HTTPException(status_code=403, detail="Tenant access denied")

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            detail = await client.get(f"/api/v1/observables/{obs_id}", headers=registered_analyst["headers"])
            enrich = await client.post(
                f"/api/v1/observables/{obs_id}/enrichments",
                json={"source": "vt", "data": {"score": 5}},
                headers=registered_analyst["headers"],
            )
        finally:
            app.state.tenant_access_validators = original_validators

        assert detail.status_code == 403
        assert enrich.status_code == 403
