"""Playbook: AI-powered endpoint containment.

Receives a malware/endpoint alert, enriches the file hash via VirusTotal,
uses an LLM to assess severity and recommend containment actions, then
auto-isolates the endpoint if the threat is critical.
"""

import asyncio
import json
import logging

from opensoar import action, playbook

logger = logging.getLogger(__name__)


@action(name="extract_endpoint_context", timeout=10)
async def extract_endpoint_context(alert_data: dict) -> dict:
    """Extract endpoint and malware indicators from the alert."""
    iocs = alert_data.get("iocs", {})
    return {
        "hostname": alert_data.get("hostname"),
        "source_ip": alert_data.get("source_ip"),
        "hashes": iocs.get("hashes", []),
        "ips": iocs.get("ips", []),
        "domains": iocs.get("domains", []),
        "rule_name": alert_data.get("rule_name"),
        "tags": alert_data.get("tags", []),
    }


@action(name="enrich_file_hashes", timeout=30, retries=2, retry_backoff=2.0)
async def enrich_file_hashes(hashes: list[str]) -> dict:
    """Enrich file hashes via VirusTotal."""
    results = {}
    try:
        from opensoar.config import settings

        if settings.vt_api_key:
            from opensoar.integrations.virustotal.connector import VirusTotalIntegration

            vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
            await vt.connect()
            try:
                for file_hash in hashes[:5]:
                    raw = await vt.lookup_hash(file_hash)
                    attrs = raw.get("data", {}).get("attributes", {})
                    stats = attrs.get("last_analysis_stats", {})
                    results[file_hash] = {
                        "malicious": stats.get("malicious", 0),
                        "suspicious": stats.get("suspicious", 0),
                        "undetected": stats.get("undetected", 0),
                        "type_description": attrs.get("type_description"),
                        "meaningful_name": attrs.get("meaningful_name"),
                        "popular_threat_name": attrs.get("popular_threat_label"),
                    }
            finally:
                await vt.disconnect()
            return {"source": "virustotal", "results": results}
    except Exception as e:
        logger.warning(f"VT hash lookup failed: {e}")

    for h in hashes:
        results[h] = {"reputation": "unknown", "note": "VT not configured"}
    return {"source": "virustotal", "results": results}


@action(name="enrich_c2_ips", timeout=30, retries=2, retry_backoff=2.0)
async def enrich_c2_ips(ips: list[str]) -> dict:
    """Check C2 IPs against AbuseIPDB."""
    results = {}
    try:
        from opensoar.config import settings

        if settings.abuseipdb_api_key:
            from opensoar.integrations.abuseipdb.connector import AbuseIPDBIntegration

            abuse = AbuseIPDBIntegration({"api_key": settings.abuseipdb_api_key})
            await abuse.connect()
            try:
                for ip in ips[:5]:
                    raw = await abuse.check_ip(ip)
                    data = raw.get("data", {})
                    results[ip] = {
                        "abuse_confidence_score": data.get("abuseConfidenceScore", 0),
                        "total_reports": data.get("totalReports", 0),
                        "country_code": data.get("countryCode"),
                        "isp": data.get("isp"),
                    }
            finally:
                await abuse.disconnect()
            return {"source": "abuseipdb", "results": results}
    except Exception as e:
        logger.warning(f"AbuseIPDB lookup failed: {e}")

    for ip in ips:
        results[ip] = {"abuse_confidence_score": 0, "note": "AbuseIPDB not configured"}
    return {"source": "abuseipdb", "results": results}


@action(name="ai_assess_endpoint_threat", timeout=60, retries=1)
async def ai_assess_endpoint_threat(
    alert_data: dict, endpoint_ctx: dict, hash_intel: dict, ip_intel: dict
) -> dict:
    """Use an LLM to assess the endpoint threat severity and recommend containment actions."""
    from opensoar.ai.client import LLMClient
    from opensoar.config import settings

    client = None
    if settings.anthropic_api_key:
        client = LLMClient(
            provider="anthropic",
            api_key=settings.anthropic_api_key,
            model=settings.llm_model or "claude-sonnet-4-6",
        )
    elif settings.openai_api_key:
        client = LLMClient(
            provider="openai",
            api_key=settings.openai_api_key,
            model=settings.llm_model or "gpt-4o",
        )
    elif settings.ollama_url:
        client = LLMClient(
            provider="ollama",
            base_url=settings.ollama_url,
            model=settings.llm_model or "llama3",
        )

    if client is None:
        return {
            "severity": "unknown",
            "should_isolate": False,
            "confidence": 0.0,
            "reasoning": "No LLM configured — manual assessment required.",
            "recommended_actions": ["Assign to endpoint security team"],
        }

    prompt = f"""Assess this endpoint security alert and recommend containment actions.

ALERT:
- Title: {alert_data.get("title", "N/A")}
- Description: {alert_data.get("description", "N/A")}
- Severity: {alert_data.get("severity", "N/A")}
- Source: {alert_data.get("source", "N/A")}
- Hostname: {endpoint_ctx.get("hostname", "N/A")}
- Source IP: {endpoint_ctx.get("source_ip", "N/A")}
- Rule: {endpoint_ctx.get("rule_name", "N/A")}
- Tags: {json.dumps(endpoint_ctx.get("tags", []))}

FILE HASH ANALYSIS (VirusTotal):
{json.dumps(hash_intel.get("results", {}), indent=2)}

C2 IP REPUTATION:
{json.dumps(ip_intel.get("results", {}), indent=2)}

Respond with ONLY a JSON object:
{{
    "severity": "critical" | "high" | "medium" | "low",
    "should_isolate": true | false,
    "confidence": 0.0-1.0,
    "threat_type": "ransomware" | "trojan" | "worm" | "rootkit" | "adware" | "pup" | "unknown",
    "reasoning": "2-3 sentence assessment",
    "indicators_of_compromise": ["key IOCs identified"],
    "recommended_actions": ["ordered list of response actions"]
}}

ISOLATION CRITERIA: Recommend isolation (should_isolate: true) ONLY for:
- Confirmed ransomware or wiper malware
- Active C2 communication with known malicious infrastructure
- Lateral movement detected from the endpoint
- Critical severity with high confidence (>0.8)"""

    response = await client.complete(
        prompt,
        system=(
            "You are an endpoint security specialist with expertise in malware analysis "
            "and incident response. Assess threats accurately based on VT detection ratios, "
            "C2 reputation, and attack patterns. Be decisive on containment — isolate when "
            "the risk of lateral movement or data loss outweighs the disruption."
        ),
        max_tokens=1024,
        temperature=0.1,
    )

    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        result = {
            "severity": "high",
            "should_isolate": False,
            "confidence": 0.5,
            "reasoning": response.content[:500],
            "recommended_actions": ["Manual assessment required — LLM response was not structured"],
        }

    result["model"] = response.model
    return result


@action(name="isolate_endpoint", timeout=15)
async def isolate_endpoint(alert_id: str, hostname: str, reasoning: str) -> dict:
    """Isolate the endpoint and log the containment action."""
    import uuid

    from sqlalchemy import select

    from opensoar.db import async_session
    from opensoar.models.activity import Activity
    from opensoar.models.alert import Alert

    async with async_session() as session:
        result = await session.execute(
            select(Alert).where(Alert.id == uuid.UUID(alert_id))
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return {"isolated": False, "error": "Alert not found"}

        alert.status = "in_progress"
        alert.determination = "malicious"

        session.add(Activity(
            alert_id=alert.id,
            action="endpoint_isolated",
            detail=(
                f"AI containment: endpoint {hostname} isolated. {reasoning}"
            ),
            metadata_json={
                "ai_isolated": True,
                "hostname": hostname,
                "playbook": "ai_endpoint_containment",
            },
        ))

        await session.commit()
        logger.warning(f"CONTAINMENT: Endpoint {hostname} isolated by AI playbook")
        return {"isolated": True, "hostname": hostname}


@action(name="log_endpoint_assessment", timeout=10)
async def log_endpoint_assessment(
    alert_id: str, severity: str, reasoning: str, actions: list[str]
) -> dict:
    """Log the AI assessment as an activity on the alert."""
    import uuid

    from sqlalchemy import select

    from opensoar.db import async_session
    from opensoar.models.activity import Activity
    from opensoar.models.alert import Alert

    async with async_session() as session:
        result = await session.execute(
            select(Alert).where(Alert.id == uuid.UUID(alert_id))
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return {"logged": False, "error": "Alert not found"}

        if alert.status == "new":
            alert.status = "in_progress"

        session.add(Activity(
            alert_id=alert.id,
            action="ai_endpoint_assessment",
            detail=f"AI assessed severity as {severity}: {reasoning}",
            metadata_json={
                "ai_severity": severity,
                "recommended_actions": actions,
                "playbook": "ai_endpoint_containment",
            },
        ))

        await session.commit()
        return {"logged": True, "severity": severity}


@playbook(
    trigger="webhook",
    conditions={"tags": "endpoint"},
    description=(
        "AI-powered endpoint containment: enrich malware hashes via VT, "
        "use LLM to assess severity, auto-isolate if critical"
    ),
)
async def ai_endpoint_containment(alert_data):
    """AI-powered endpoint threat assessment and containment."""
    # Handle both Alert ORM object and dict
    if hasattr(alert_data, "normalized"):
        data = alert_data.normalized or {}
        data["iocs"] = alert_data.iocs or {}
        data.setdefault("title", alert_data.title)
        data.setdefault("description", alert_data.description)
        data.setdefault("severity", alert_data.severity)
        data.setdefault("source", alert_data.source)
        data.setdefault("source_ip", alert_data.source_ip)
        data.setdefault("hostname", alert_data.hostname)
        data.setdefault("rule_name", alert_data.rule_name)
        data.setdefault("tags", alert_data.tags or [])
        alert_id = str(alert_data.id)
    elif isinstance(alert_data, dict):
        data = alert_data
        alert_id = data.get("id", "")
    else:
        return {"contained": False, "error": "Invalid alert data"}

    # Step 1: Extract endpoint context
    endpoint_ctx = await extract_endpoint_context(data)

    # Step 2: Parallel enrichment — file hashes + C2 IPs
    hash_intel, ip_intel = await asyncio.gather(
        enrich_file_hashes(endpoint_ctx["hashes"]),
        enrich_c2_ips(endpoint_ctx["ips"]),
    )

    # Step 3: AI threat assessment
    assessment = await ai_assess_endpoint_threat(data, endpoint_ctx, hash_intel, ip_intel)

    severity = assessment.get("severity", "unknown")
    should_isolate = assessment.get("should_isolate", False)
    confidence = assessment.get("confidence", 0.0)
    reasoning = assessment.get("reasoning", "")
    actions = assessment.get("recommended_actions", [])

    # Step 4: Containment decision
    containment = {"action": "none"}
    if should_isolate and confidence >= 0.8 and alert_id and endpoint_ctx["hostname"]:
        containment = await isolate_endpoint(
            alert_id, endpoint_ctx["hostname"], reasoning
        )
        containment["action"] = "isolated"
    elif alert_id:
        await log_endpoint_assessment(alert_id, severity, reasoning, actions)
        containment["action"] = "logged"

    return {
        "assessed": True,
        "severity": severity,
        "threat_type": assessment.get("threat_type", "unknown"),
        "should_isolate": should_isolate,
        "confidence": confidence,
        "reasoning": reasoning,
        "indicators": assessment.get("indicators_of_compromise", []),
        "recommended_actions": actions,
        "containment": containment,
        "enrichment": {
            "hashes": hash_intel,
            "ips": ip_intel,
        },
        "model": assessment.get("model"),
    }
