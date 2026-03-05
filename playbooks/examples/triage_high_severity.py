"""Example playbook: Triage high-severity alerts.

This playbook demonstrates the core OpenSOAR concepts:
- @playbook decorator for trigger-based execution
- @action decorator for tracked, retryable actions
- asyncio.gather for parallel execution
- Conditional response logic
"""

import asyncio
import logging

from opensoar import action, playbook

logger = logging.getLogger(__name__)


@action(name="enrich_virustotal", timeout=30, retries=2, retry_backoff=2.0)
async def enrich_virustotal(iocs: dict) -> dict:
    """Enrich IOCs with VirusTotal data."""
    ips = iocs.get("ips", [])
    results = {}
    for ip in ips:
        # In production, this calls the real VT API via the integration
        results[ip] = {"reputation": "unknown", "source": "virustotal"}
        logger.info(f"VirusTotal lookup: {ip}")
    return {"source": "virustotal", "results": results}


@action(name="enrich_abuseipdb", timeout=30, retries=2, retry_backoff=2.0)
async def enrich_abuseipdb(source_ip: str | None) -> dict:
    """Check source IP on AbuseIPDB."""
    if not source_ip:
        return {"source": "abuseipdb", "result": "no_ip"}
    # In production, this calls the real AbuseIPDB API
    logger.info(f"AbuseIPDB lookup: {source_ip}")
    return {"source": "abuseipdb", "ip": source_ip, "abuse_score": 0}


@action(name="calculate_risk", timeout=5)
async def calculate_risk(alert_data: dict, vt_result: dict, abuse_result: dict) -> dict:
    """Calculate risk score based on enrichment data."""
    score = 0.0

    severity = alert_data.get("severity", "medium")
    if severity == "critical":
        score += 0.5
    elif severity == "high":
        score += 0.3
    elif severity == "medium":
        score += 0.1

    abuse_score = abuse_result.get("abuse_score", 0)
    if abuse_score > 80:
        score += 0.4
    elif abuse_score > 50:
        score += 0.2

    return {"risk_score": min(score, 1.0), "details": "Auto-calculated"}


@action(name="notify_soc", timeout=15, retries=1)
async def notify_soc(alert_data: dict, risk: dict) -> dict:
    """Send notification to SOC team."""
    title = alert_data.get("title", "Unknown Alert")
    score = risk.get("risk_score", 0)
    logger.info(f"SOC notification: [{score:.1f}] {title}")
    return {"notified": True, "channel": "#soc-alerts"}


@playbook(
    trigger="webhook",
    conditions={"severity": ["high", "critical"]},
    description="Automatically triage high-severity alerts with enrichment and risk scoring",
)
async def triage_high_severity(alert_data):
    """Main triage playbook for high-severity alerts."""
    # Handle both Alert model and dict
    if hasattr(alert_data, "normalized"):
        data = alert_data.normalized
        iocs = alert_data.iocs or {}
        source_ip = alert_data.source_ip
    elif isinstance(alert_data, dict):
        data = alert_data
        iocs = alert_data.get("iocs", {})
        source_ip = alert_data.get("source_ip")
    else:
        data = {}
        iocs = {}
        source_ip = None

    # Parallel enrichment
    vt_result, abuse_result = await asyncio.gather(
        enrich_virustotal(iocs),
        enrich_abuseipdb(source_ip),
    )

    # Risk scoring
    risk = await calculate_risk(data, vt_result, abuse_result)

    # Conditional response
    if risk["risk_score"] > 0.5:
        await notify_soc(data, risk)

    return {
        "enrichment": {
            "virustotal": vt_result,
            "abuseipdb": abuse_result,
        },
        "risk": risk,
        "auto_triaged": True,
    }
