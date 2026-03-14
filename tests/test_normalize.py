"""Tests for alert normalization and IOC extraction."""
from __future__ import annotations


from opensoar.ingestion.normalize import (
    _looks_like_ip,
    extract_field,
    extract_iocs,
    normalize_alert,
    normalize_severity,
)


# ── normalize_severity ──────────────────────────────────────


class TestNormalizeSeverity:
    def test_direct_values(self):
        assert normalize_severity("critical") == "critical"
        assert normalize_severity("high") == "high"
        assert normalize_severity("medium") == "medium"
        assert normalize_severity("low") == "low"

    def test_keywords(self):
        assert normalize_severity("crit") == "critical"
        assert normalize_severity("error") == "high"
        assert normalize_severity("warning") == "medium"
        assert normalize_severity("warn") == "medium"
        assert normalize_severity("info") == "low"
        assert normalize_severity("informational") == "low"

    def test_case_insensitive(self):
        assert normalize_severity("CRITICAL") == "critical"
        assert normalize_severity("High") == "high"
        assert normalize_severity("  Medium  ") == "medium"

    def test_numeric_strings(self):
        assert normalize_severity("1") == "low"
        assert normalize_severity("2") == "medium"
        assert normalize_severity("3") == "high"
        assert normalize_severity("4") == "critical"
        assert normalize_severity("5") == "critical"

    def test_numeric_values(self):
        assert normalize_severity(1) == "low"
        assert normalize_severity(4) == "critical"

    def test_none_default(self):
        assert normalize_severity(None) == "medium"

    def test_unknown_default(self):
        assert normalize_severity("foo") == "medium"
        assert normalize_severity("xyz") == "medium"


# ── extract_field ───────────────────────────────────────────


class TestExtractField:
    def test_top_level(self):
        assert extract_field({"a": 1}, "a") == 1

    def test_nested(self):
        assert extract_field({"a": {"b": {"c": 3}}}, "a.b.c") == 3

    def test_fallback_paths(self):
        payload = {"source": {"ip": "1.2.3.4"}}
        assert extract_field(payload, "src_ip", "source.ip") == "1.2.3.4"

    def test_default(self):
        assert extract_field({}, "missing", default="fallback") == "fallback"

    def test_none_returns_default(self):
        # extract_field treats None as "not found" and falls through to default
        assert extract_field({"a": None}, "a", default="x") == "x"

    def test_first_match_wins(self):
        payload = {"a": 1, "b": 2}
        assert extract_field(payload, "a", "b") == 1


# ── extract_iocs ────────────────────────────────────────────


class TestExtractIOCs:
    def test_extracts_ips(self):
        payload = {"source_ip": "192.168.1.1", "dest_ip": "10.0.0.1"}
        iocs = extract_iocs(payload)
        assert "192.168.1.1" in iocs["ips"]
        assert "10.0.0.1" in iocs["ips"]

    def test_extracts_hashes(self):
        payload = {"file_hash": "abc123", "md5": "def456"}
        iocs = extract_iocs(payload)
        assert "abc123" in iocs["hashes"]
        assert "def456" in iocs["hashes"]

    def test_extracts_domains(self):
        payload = {"domain": "evil.example.com"}
        iocs = extract_iocs(payload)
        assert "evil.example.com" in iocs["domains"]

    def test_extracts_urls(self):
        payload = {"url": "https://evil.example.com/malware"}
        iocs = extract_iocs(payload)
        assert "https://evil.example.com/malware" in iocs["urls"]

    def test_nested_extraction(self):
        payload = {"network": {"source": {"ip": "1.2.3.4"}}}
        iocs = extract_iocs(payload)
        assert "1.2.3.4" in iocs.get("ips", [])

    def test_empty_payload(self):
        iocs = extract_iocs({})
        assert iocs == {}

    def test_deduplication(self):
        payload = {"source_ip": "1.2.3.4", "client_ip": "1.2.3.4"}
        iocs = extract_iocs(payload)
        assert iocs["ips"].count("1.2.3.4") == 1

    def test_depth_limit(self):
        # Build deeply nested payload
        payload: dict = {}
        current = payload
        for i in range(15):
            current[f"level_{i}"] = {}
            current = current[f"level_{i}"]
        current["source_ip"] = "1.2.3.4"

        iocs = extract_iocs(payload)
        # Should not extract from depth > 10
        assert "ips" not in iocs or "1.2.3.4" not in iocs.get("ips", [])


# ── _looks_like_ip ──────────────────────────────────────────


class TestLooksLikeIP:
    def test_valid_ips(self):
        assert _looks_like_ip("192.168.1.1") is True
        assert _looks_like_ip("10.0.0.1") is True
        assert _looks_like_ip("0.0.0.0") is True
        assert _looks_like_ip("255.255.255.255") is True

    def test_invalid_ips(self):
        assert _looks_like_ip("256.1.1.1") is False
        assert _looks_like_ip("1.2.3") is False
        assert _looks_like_ip("not.an.ip.addr") is False
        assert _looks_like_ip("") is False
        assert _looks_like_ip("1.2.3.4.5") is False


# ── normalize_alert ─────────────────────────────────────────


class TestNormalizeAlert:
    def test_generic_webhook(self):
        payload = {
            "rule_name": "Suspicious Login",
            "severity": "high",
            "source_ip": "10.0.0.42",
            "hostname": "db-prod-01",
            "tags": ["auth"],
        }
        result = normalize_alert(payload, source="webhook")
        assert result["title"] == "Suspicious Login"
        assert result["severity"] == "high"
        assert result["source_ip"] == "10.0.0.42"
        assert result["hostname"] == "db-prod-01"
        assert result["status"] == "new"

    def test_elastic_format(self):
        payload = {
            "rule": {"name": "Elastic Rule", "severity": "critical"},
            "source": {"ip": "172.16.0.1"},
            "host": {"name": "elastic-node"},
        }
        result = normalize_alert(payload, source="elastic")
        assert result["title"] == "Elastic Rule"
        assert result["severity"] == "critical"
        assert result["source_ip"] == "172.16.0.1"
        assert result["hostname"] == "elastic-node"

    def test_missing_title_default(self):
        result = normalize_alert({}, source="webhook")
        assert result["title"] == "Untitled Alert"

    def test_severity_inference_from_process(self):
        payload = {"process": {"name": "nc"}, "title": "Netcat Connection"}
        result = normalize_alert(payload)
        assert result["severity"] == "high"

    def test_severity_inference_auth_failure(self):
        payload = {
            "event": {"category": "authentication", "outcome": "failure"},
            "title": "Failed Login",
        }
        result = normalize_alert(payload)
        assert result["severity"] == "medium"

    def test_partner_extraction(self):
        payload = {"title": "Test", "partner": "acme-corp"}
        result = normalize_alert(payload)
        assert result["partner"] == "acme-corp"

    def test_tenant_as_partner(self):
        payload = {"title": "Test", "tenant": "globex"}
        result = normalize_alert(payload)
        assert result["partner"] == "globex"

    def test_source_dict_not_used_as_string(self):
        """Elastic payloads have source as a dict — should fall back to the source param."""
        payload = {
            "rule": {"name": "Elastic Rule"},
            "source": {"ip": "172.16.0.1"},
        }
        result = normalize_alert(payload, source="elastic")
        assert result["source"] == "elastic"
        assert isinstance(result["source"], str)
