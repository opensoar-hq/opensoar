from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

SEVERITY_KEYWORDS = {
    "critical": ["critical", "crit"],
    "high": ["high", "3", "error"],
    "medium": ["medium", "med", "2", "warning", "warn"],
    "low": ["low", "1", "info", "informational"],
}


def normalize_severity(value: Any) -> str:
    if value is None:
        return "medium"

    val = str(value).lower().strip()

    for severity, keywords in SEVERITY_KEYWORDS.items():
        if val in keywords or val == severity:
            return severity

    try:
        num = int(val)
        if num >= 4:
            return "critical"
        elif num == 3:
            return "high"
        elif num == 2:
            return "medium"
        else:
            return "low"
    except ValueError:
        pass

    return "medium"


def extract_field(payload: dict, *field_paths: str, default: Any = None) -> Any:
    for path in field_paths:
        parts = path.split(".")
        current = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = None
                break
        if current is not None:
            return current
    return default


def normalize_alert(payload: dict, source: str = "webhook") -> dict:
    title = extract_field(
        payload,
        "rule_name",
        "rule.name",
        "alert.rule.name",
        "title",
        "name",
        "signal.rule.name",
        "message",
        default="Untitled Alert",
    )

    raw_severity = extract_field(
        payload,
        "severity",
        "rule.severity",
        "alert.severity",
        "signal.rule.severity",
        "level",
        "priority",
    )

    # Infer severity from event context if not explicitly set
    if raw_severity is None:
        event_category = extract_field(payload, "event.category", default="")
        event_outcome = extract_field(payload, "event.outcome", default="")
        process_name = extract_field(payload, "process.name", default="")

        if process_name in ("nc", "ncat", "bash", "sh", "powershell", "cmd"):
            raw_severity = "high"
        elif event_outcome == "failure" and event_category == "authentication":
            raw_severity = "medium"
        elif event_category == "process":
            raw_severity = "medium"
        elif event_category == "file":
            raw_severity = "medium"

    severity = normalize_severity(raw_severity)

    raw_source = extract_field(payload, "source", default=source)
    # Elastic payloads have "source" as a dict (e.g. {"ip": "..."}), not a string
    alert_source = raw_source if isinstance(raw_source, str) else source

    return {
        "source": alert_source,
        "source_id": extract_field(payload, "source_id", "id", "_id", "alert_id", "signal.id"),
        "title": str(title),
        "description": extract_field(
            payload, "description", "message", "rule.description", "alert.description"
        ),
        "severity": severity,
        "status": "new",
        "source_ip": extract_field(
            payload,
            "source_ip",
            "source.ip",
            "src_ip",
            "client.ip",
            "signal.source.ip",
        ),
        "dest_ip": extract_field(
            payload,
            "dest_ip",
            "destination.ip",
            "dst_ip",
            "server.ip",
            "signal.destination.ip",
        ),
        "hostname": extract_field(
            payload,
            "hostname",
            "host.name",
            "agent.name",
            "computer_name",
            "signal.host.name",
        ),
        "rule_name": str(title),
        "iocs": extract_iocs(payload),
        "tags": extract_field(payload, "tags", "rule.tags", default=[]),
        "partner": extract_field(payload, "partner", "tenant", "customer", "organization"),
    }


def extract_iocs(payload: dict) -> dict:
    iocs: dict[str, list[str]] = {"ips": [], "domains": [], "hashes": [], "urls": []}

    def _walk(obj: Any, depth: int = 0) -> None:
        if depth > 10:
            return
        if isinstance(obj, dict):
            for key, val in obj.items():
                if isinstance(val, str):
                    k = key.lower()
                    if "ip" in k and _looks_like_ip(val):
                        iocs["ips"].append(val)
                    elif "hash" in k or k in ("md5", "sha1", "sha256"):
                        iocs["hashes"].append(val)
                    elif "domain" in k or "host" in k:
                        if "." in val and not _looks_like_ip(val):
                            iocs["domains"].append(val)
                    elif "url" in k and val.startswith(("http://", "https://")):
                        iocs["urls"].append(val)
                else:
                    _walk(val, depth + 1)
            return
        if isinstance(obj, list):
            for item in obj:
                _walk(item, depth + 1)

    _walk(payload)

    return {k: list(set(v)) for k, v in iocs.items() if v}


def _looks_like_ip(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
