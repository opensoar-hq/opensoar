"""Prompt templates for AI features."""
from __future__ import annotations

import json
from typing import Any


def build_summarize_prompt(alert: dict[str, Any]) -> str:
    """Build a prompt that asks an LLM to summarize an alert."""
    parts = [
        "Summarize this security alert in 2-3 sentences for a SOC analyst.",
        "Focus on: what happened, what's affected, and how severe it is.",
        "",
        f"Title: {alert.get('title', 'N/A')}",
        f"Severity: {alert.get('severity', 'N/A')}",
    ]

    if alert.get("description"):
        parts.append(f"Description: {alert['description']}")
    if alert.get("source_ip"):
        parts.append(f"Source IP: {alert['source_ip']}")
    if alert.get("dest_ip"):
        parts.append(f"Destination IP: {alert['dest_ip']}")
    if alert.get("hostname"):
        parts.append(f"Hostname: {alert['hostname']}")
    if alert.get("rule_name"):
        parts.append(f"Rule: {alert['rule_name']}")
    if alert.get("iocs"):
        parts.append(f"IOCs: {json.dumps(alert['iocs'])}")
    if alert.get("tags"):
        parts.append(f"Tags: {', '.join(alert['tags'])}")

    return "\n".join(parts)


def build_triage_prompt(alert: dict[str, Any]) -> str:
    """Build a prompt that asks an LLM to suggest severity and determination."""
    alert_json = json.dumps(
        {k: v for k, v in alert.items() if k not in ("id", "created_at", "updated_at")},
        indent=2,
        default=str,
    )

    return f"""Analyze this security alert and suggest a triage classification.

Respond with ONLY a JSON object (no markdown, no explanation) with these fields:
- "severity": one of "critical", "high", "medium", "low"
- "determination": one of "malicious", "suspicious", "benign", "unknown"
- "confidence": a float between 0.0 and 1.0
- "reasoning": a brief explanation (1-2 sentences)

Alert data:
{alert_json}"""


def build_ioc_context_prompt(
    ioc_type: str,
    ioc_value: str,
    enrichments: list[dict[str, Any]],
) -> str:
    """Build a prompt that synthesizes IOC enrichment data into a context summary."""
    enrichment_text = ""
    for e in enrichments:
        enrichment_text += f"\n--- {e.get('source', 'Unknown source')} ---\n"
        enrichment_text += json.dumps(e.get("data", {}), indent=2, default=str)

    return f"""Synthesize the following enrichment data for a security IOC into a brief analyst-readable summary.

IOC Type: {ioc_type}
IOC Value: {ioc_value}

Enrichment results:
{enrichment_text}

Provide:
1. A 1-2 sentence verdict (malicious, suspicious, or benign)
2. Key findings from each source
3. Recommended actions"""
