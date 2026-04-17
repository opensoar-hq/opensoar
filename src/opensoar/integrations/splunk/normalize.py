"""Normalize Splunk notable-event payloads into OpenSOAR alert shape."""
from __future__ import annotations

from typing import Any

from opensoar.ingestion.normalize import extract_field, extract_iocs, normalize_severity


def normalize_splunk_notable(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a Splunk notable event (ES or savedsearch webhook) into an alert dict.

    Splunk webhooks typically wrap the event under ``result`` with top-level
    ``search_name``; the ES notable framework uses fields like ``rule_name``,
    ``urgency``, ``src``, ``dest``, ``host``.
    """
    result = payload.get("result") if isinstance(payload.get("result"), dict) else payload

    title = (
        extract_field(result, "rule_name", "signature", "search_name")
        or extract_field(payload, "search_name")
        or "Splunk Notable"
    )

    raw_severity = extract_field(
        result,
        "severity",
        "urgency",
        "priority",
    )

    source_ip = extract_field(result, "src_ip", "src", "source_ip")
    dest_ip = extract_field(result, "dest_ip", "dest", "destination_ip")
    hostname = extract_field(result, "host", "hostname", "dvc")

    return {
        "source": "splunk",
        "source_id": extract_field(
            result, "event_id", "event_hash", "_cd", "sid"
        ),
        "title": str(title),
        "description": extract_field(result, "description", "_raw"),
        "severity": normalize_severity(raw_severity),
        "status": "new",
        "source_ip": source_ip,
        "dest_ip": dest_ip,
        "hostname": hostname,
        "rule_name": str(title),
        "iocs": extract_iocs(result),
        "tags": result.get("tag", []) if isinstance(result.get("tag"), list) else [],
    }
