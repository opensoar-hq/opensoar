"""Normalizer for Microsoft Defender for Endpoint alert payloads.

Accepts both raw Defender alert objects (as returned by ``/api/alerts``) and
webhook wrappers that nest the alert under an ``alert`` key.
"""
from __future__ import annotations

from typing import Any

from opensoar.ingestion.normalize import extract_field, extract_iocs, normalize_severity


def normalize_msdefender_alert(payload: dict[str, Any]) -> dict[str, Any]:
    alert = payload.get("alert", payload)

    title = (
        extract_field(alert, "title", "alertDisplayName", "threatName")
        or "Microsoft Defender Alert"
    )
    severity = normalize_severity(extract_field(alert, "severity"))
    source_id = extract_field(alert, "id", "alertId", "incidentId")

    hostname = extract_field(
        alert, "computerDnsName", "machineDnsName", "deviceName", "machineId"
    )
    source_ip = extract_field(alert, "sourceIp", "lastSeenIpAddress", "ipAddress")

    category = extract_field(alert, "category")
    detection_source = extract_field(alert, "detectionSource")
    tags_raw = extract_field(alert, "tags", default=[])
    tags: list[str] = list(tags_raw) if isinstance(tags_raw, list) else []
    if category and category not in tags:
        tags.append(str(category))
    if detection_source and detection_source not in tags:
        tags.append(str(detection_source))

    return {
        "source": "msdefender",
        "source_id": source_id,
        "title": str(title),
        "description": extract_field(alert, "description", "alertDescription"),
        "severity": severity,
        "status": "new",
        "source_ip": source_ip,
        "dest_ip": extract_field(alert, "destinationIp"),
        "hostname": hostname,
        "rule_name": str(title),
        "iocs": extract_iocs(alert),
        "tags": tags,
    }
