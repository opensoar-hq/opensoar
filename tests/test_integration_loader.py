"""Tests for dynamic integration loading and the integration type registry."""
from __future__ import annotations

from opensoar.integrations.loader import IntegrationLoader


class TestIntegrationLoader:
    def test_discovers_builtin_connectors(self):
        """Should find all built-in integration connectors."""
        loader = IntegrationLoader()
        loader.discover_builtin()
        types = loader.available_types()
        assert "elastic" in types
        assert "virustotal" in types
        assert "abuseipdb" in types
        assert "slack" in types

    def test_get_connector_class(self):
        """Should return the connector class for a known type."""
        loader = IntegrationLoader()
        loader.discover_builtin()
        cls = loader.get_connector("elastic")
        assert cls is not None
        assert cls.integration_type == "elastic"

    def test_get_unknown_returns_none(self):
        """Should return None for unknown integration types."""
        loader = IntegrationLoader()
        assert loader.get_connector("nonexistent") is None

    def test_available_types_includes_metadata(self):
        """available_types_detail() should include display_name and description."""
        loader = IntegrationLoader()
        loader.discover_builtin()
        details = loader.available_types_detail()
        assert len(details) >= 4
        for entry in details:
            assert "type" in entry
            assert "display_name" in entry
            assert "description" in entry

    def test_register_custom_connector(self):
        """Should be able to register a custom connector class."""
        loader = IntegrationLoader()

        class FakeIntegration:
            integration_type = "fake"
            display_name = "Fake"
            description = "Test"

        loader.register("fake", FakeIntegration)
        assert "fake" in loader.available_types()
        assert loader.get_connector("fake") is FakeIntegration


class TestAvailableTypesAPI:
    async def test_list_available_types(self, client):
        """GET /integrations/types should return available integration types."""
        resp = await client.get("/api/v1/integrations/types")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 4
        types = [d["type"] for d in data]
        assert "elastic" in types
