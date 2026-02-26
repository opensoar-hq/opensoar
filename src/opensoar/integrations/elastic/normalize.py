from __future__ import annotations

from opensoar.ingestion.normalize import extract_field, extract_iocs, normalize_severity


def normalize_elastic_alert(payload: dict) -> dict:
    signal = payload.get("signal", payload)
    rule = signal.get("rule", payload.get("rule", {}))

    title = (
        rule.get("name")
        or extract_field(payload, "kibana.alert.rule.name", "rule_name")
        or "Elastic Alert"
    )

    severity = normalize_severity(
        rule.get("severity")
        or extract_field(payload, "kibana.alert.severity", "signal.rule.severity")
    )

    return {
        "source": "elastic",
        "source_id": extract_field(
            payload, "_id", "kibana.alert.uuid", "signal.id"
        ),
        "title": str(title),
        "description": rule.get("description"),
        "severity": severity,
        "status": "new",
        "source_ip": extract_field(
            payload,
            "source.ip",
            "signal.source.ip",
            "kibana.alert.original_event.source.ip",
        ),
        "dest_ip": extract_field(
            payload,
            "destination.ip",
            "signal.destination.ip",
        ),
        "hostname": extract_field(
            payload,
            "host.name",
            "agent.name",
            "signal.host.name",
        ),
        "rule_name": str(title),
        "iocs": extract_iocs(payload),
        "tags": rule.get("tags", []),
    }
