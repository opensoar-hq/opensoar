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


def build_playbook_prompt(description: str) -> str:
    """Build a prompt that generates a Python playbook from natural language."""
    return f"""Generate an OpenSOAR playbook in Python based on the following description.

Use the OpenSOAR decorator pattern:
- @playbook(trigger="...", conditions={{...}}) for the main function
- @action(name="...", timeout=30, retries=2) for individual actions
- Use asyncio.gather() for parallel execution
- Use async/await throughout

Description:
{description}

Respond with ONLY the Python code (no markdown fences, no explanation).
Include imports at the top. The playbook should be production-ready."""


def build_auto_resolve_prompt(alerts: list[dict[str, Any]]) -> str:
    """Build a prompt that decides whether alerts can be auto-resolved as benign."""
    alerts_json = json.dumps(alerts, indent=2, default=str)

    return f"""Analyze these security alerts and determine if each can be safely auto-resolved as benign.

For each alert, respond with a JSON array where each element has:
- "alert_index": the index in the input array (0-based)
- "should_resolve": boolean — true ONLY if you are confident this is benign
- "confidence": float 0.0-1.0 — your confidence in the decision
- "determination": "benign" or "suspicious" or "malicious"
- "reasoning": brief explanation

Be CONSERVATIVE — only mark as should_resolve:true if confidence > 0.85 and clearly benign.
When in doubt, set should_resolve:false so a human analyst reviews it.

Respond with ONLY a JSON array (no markdown, no explanation).

Alerts:
{alerts_json}"""


def build_recommendation_prompt(
    alert: dict[str, Any],
    observables: list[dict[str, Any]],
    similar_alerts: list[dict[str, Any]],
) -> str:
    """Build a prompt that asks an LLM what a seasoned analyst would do next."""
    alert_json = json.dumps(
        {k: v for k, v in alert.items() if k not in ("id", "created_at", "updated_at")},
        indent=2,
        default=str,
    )
    observables_json = (
        json.dumps(observables, indent=2, default=str) if observables else "(none)"
    )
    similar_json = (
        json.dumps(similar_alerts, indent=2, default=str) if similar_alerts else "(none)"
    )

    return f"""You are a senior SOC analyst deciding the next action for an alert.

Choose exactly ONE action from this vocabulary:
- "isolate": quarantine the affected host from the network
- "block": block the offending indicator (IP/domain/hash) at the perimeter
- "enrich": gather more context before deciding (IOC lookups, user history, etc.)
- "escalate": hand off to a human analyst or IR team
- "resolve": close the alert as benign or already remediated

Respond with ONLY a JSON object (no markdown, no prose) with these fields:
- "action": one of "isolate", "block", "enrich", "escalate", "resolve"
- "confidence": float between 0.0 and 1.0
- "reasoning": 1-3 sentence justification grounded in the evidence below

Alert under review:
{alert_json}

Linked observables and enrichments:
{observables_json}

Similar past alerts (same source_ip, for historical context):
{similar_json}"""


def build_correlation_prompt(alerts: list[dict[str, Any]]) -> str:
    """Build a prompt that groups related alerts into potential incidents."""
    alerts_json = json.dumps(alerts, indent=2, default=str)

    return f"""Analyze these security alerts and group related ones into potential incidents.

Look for:
- Shared source/destination IPs
- Same hostname or user
- Related attack techniques (e.g., recon → exploitation → lateral movement)
- Temporal proximity
- Common IOCs

Respond with ONLY a JSON object (no markdown, no explanation):
{{
  "groups": [
    {{
      "title": "Suggested incident title",
      "alert_ids": ["id1", "id2"],
      "reasoning": "Why these alerts are related"
    }}
  ]
}}

Alerts that don't correlate with anything can be omitted.

Alerts:
{alerts_json}"""
