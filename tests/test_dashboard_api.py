from __future__ import annotations

from opensoar.plugins import register_tenant_access_validator


class TestDashboardStats:
    async def test_tenant_validator_scopes_dashboard_alert_aggregations(self, client, registered_analyst):
        from opensoar.main import app
        from opensoar.models.alert import Alert

        await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Acme Alert", "severity": "high", "partner": "acme-corp"},
        )
        await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "Globex Alert", "severity": "critical", "partner": "globex"},
        )

        async def validator(**kwargs):
            query = kwargs.get("query")
            if query is not None and kwargs["resource_type"] == "alert":
                return query.where(Alert.partner == "acme-corp")
            return None

        original_validators = list(app.state.tenant_access_validators)
        app.state.tenant_access_validators = []
        register_tenant_access_validator(app, validator)
        try:
            resp = await client.get("/api/v1/dashboard/stats", headers=registered_analyst["headers"])
        finally:
            app.state.tenant_access_validators = original_validators

        assert resp.status_code == 200
        data = resp.json()
        assert set(data["alerts_by_partner"].keys()) == {"acme-corp"}
        assert set(data["open_by_partner"].keys()) == {"acme-corp"}
        assert data["total_alerts"] >= 1
