"""Playbook: AI-powered phishing alert triage.

Receives a phishing alert, extracts IOCs (URLs, domains, IPs), checks
reputation via VirusTotal, then uses an LLM to analyze the email content,
assess legitimacy, and determine a verdict. Auto-resolves benign alerts
or escalates confirmed phishing to the SOC.
"""

import asyncio
import json
import logging

from opensoar import action, playbook

logger = logging.getLogger(__name__)


@action(name="extract_phishing_iocs", timeout=10)
async def extract_phishing_iocs(alert_data: dict) -> dict:
    """Extract phishing-relevant IOCs from the alert."""
    iocs = alert_data.get("iocs", {})
    return {
        "urls": iocs.get("urls", []),
        "domains": iocs.get("domains", []),
        "ips": iocs.get("ips", []),
        "hashes": iocs.get("hashes", []),
        "source_ip": alert_data.get("source_ip"),
        "dest_ip": alert_data.get("dest_ip"),
    }


@action(name="check_domain_reputation", timeout=30, retries=2, retry_backoff=2.0)
async def check_domain_reputation(domains: list[str]) -> dict:
    """Check domain reputation via VirusTotal if configured."""
    results = {}
    try:
        from opensoar.config import settings

        if settings.vt_api_key:
            from opensoar.integrations.virustotal.connector import VirusTotalIntegration

            vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
            await vt.connect()
            try:
                for domain in domains[:5]:  # Limit to avoid rate limits
                    raw = await vt.lookup_domain(domain)
                    attrs = raw.get("data", {}).get("attributes", {})
                    stats = attrs.get("last_analysis_stats", {})
                    results[domain] = {
                        "malicious": stats.get("malicious", 0),
                        "suspicious": stats.get("suspicious", 0),
                        "registrar": attrs.get("registrar"),
                        "creation_date": str(attrs.get("creation_date", "")),
                    }
            finally:
                await vt.disconnect()
            return {"source": "virustotal", "results": results}
    except Exception as e:
        logger.warning(f"VT domain lookup failed: {e}")

    # Fallback: return basic info without real enrichment
    for domain in domains:
        results[domain] = {"reputation": "unknown", "note": "VT not configured"}
    return {"source": "virustotal", "results": results}


@action(name="check_ip_reputation", timeout=30, retries=2, retry_backoff=2.0)
async def check_ip_reputation(ips: list[str]) -> dict:
    """Check IP reputation via AbuseIPDB if configured."""
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


@action(name="ai_analyze_phishing", timeout=60, retries=1)
async def ai_analyze_phishing(alert_data: dict, domain_intel: dict, ip_intel: dict) -> dict:
    """Use an LLM to analyze the phishing alert and enrichment data, then render a verdict."""
    from opensoar.ai.client import LLMClient
    from opensoar.config import settings

    # Build LLM client (try providers in order)
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
            "verdict": "unknown",
            "confidence": 0.0,
            "reasoning": "No LLM configured — manual review required.",
            "recommended_actions": ["Assign to analyst for manual triage"],
        }

    prompt = f"""Analyze this phishing alert and enrichment data. Determine if this is a real phishing attack.

ALERT:
- Title: {alert_data.get("title", "N/A")}
- Description: {alert_data.get("description", "N/A")}
- Severity: {alert_data.get("severity", "N/A")}
- Source: {alert_data.get("source", "N/A")}
- Source IP: {alert_data.get("source_ip", "N/A")}
- Destination IP: {alert_data.get("dest_ip", "N/A")}
- Hostname: {alert_data.get("hostname", "N/A")}
- Rule: {alert_data.get("rule_name", "N/A")}
- Tags: {json.dumps(alert_data.get("tags", []))}
- IOCs: {json.dumps(alert_data.get("iocs", {{}}))}

DOMAIN REPUTATION:
{json.dumps(domain_intel.get("results", {{}}), indent=2)}

IP REPUTATION:
{json.dumps(ip_intel.get("results", {{}}), indent=2)}

Respond with ONLY a JSON object:
{{
    "verdict": "malicious" | "suspicious" | "benign",
    "confidence": 0.0-1.0,
    "reasoning": "2-3 sentence explanation",
    "indicators": ["list of key suspicious indicators found"],
    "recommended_actions": ["list of recommended response actions"]
}}"""

    response = await client.complete(
        prompt,
        system=(
            "You are an expert email security analyst specializing in phishing detection. "
            "Analyze alerts methodically: check domain age, typosquatting, URL patterns, "
            "IP reputation, and credential harvesting indicators. Be accurate but conservative — "
            "flag uncertain cases as suspicious rather than benign."
        ),
        max_tokens=1024,
        temperature=0.1,
    )

    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        result = {
            "verdict": "suspicious",
            "confidence": 0.5,
            "reasoning": response.content[:500],
            "recommended_actions": ["Manual review required — LLM response was not structured"],
        }

    result["model"] = response.model
    return result


@action(name="auto_resolve_benign_phishing", timeout=10)
async def auto_resolve_benign(alert_id: str, reasoning: str) -> dict:
    """Auto-resolve an alert determined to be benign."""
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
            return {"resolved": False, "error": "Alert not found"}

        alert.status = "resolved"
        alert.determination = "benign"
        alert.resolve_reason = f"AI auto-resolved: {reasoning}"

        session.add(Activity(
            alert_id=alert.id,
            action="ai_auto_resolved",
            detail=f"AI phishing triage determined alert is benign: {reasoning}",
            metadata_json={"ai_resolved": True, "playbook": "ai_phishing_triage"},
        ))

        await session.commit()
        return {"resolved": True, "determination": "benign"}


@action(name="escalate_phishing_alert", timeout=15, retries=1)
async def escalate_phishing(alert_id: str, verdict: str, reasoning: str) -> dict:
    """Escalate a confirmed or suspicious phishing alert."""
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
            return {"escalated": False, "error": "Alert not found"}

        if alert.status == "new":
            alert.status = "in_progress"
        alert.determination = verdict

        session.add(Activity(
            alert_id=alert.id,
            action="ai_escalated",
            detail=f"AI phishing triage escalated ({verdict}): {reasoning}",
            metadata_json={
                "ai_escalated": True,
                "verdict": verdict,
                "playbook": "ai_phishing_triage",
            },
        ))

        await session.commit()
        return {"escalated": True, "verdict": verdict}


@playbook(
    trigger="webhook",
    conditions={"tags": "phishing"},
    description=(
        "AI-powered phishing triage: extract IOCs, check reputation, "
        "use LLM to analyze and verdict, auto-resolve or escalate"
    ),
)
async def ai_phishing_triage(alert_data):
    """AI-powered end-to-end phishing alert triage."""
    # Handle both Alert ORM object and dict
    if hasattr(alert_data, "normalized"):
        data = alert_data.normalized or {}
        data["iocs"] = alert_data.iocs or {}
        data.setdefault("title", alert_data.title)
        data.setdefault("description", alert_data.description)
        data.setdefault("severity", alert_data.severity)
        data.setdefault("source", alert_data.source)
        data.setdefault("source_ip", alert_data.source_ip)
        data.setdefault("dest_ip", alert_data.dest_ip)
        data.setdefault("hostname", alert_data.hostname)
        data.setdefault("rule_name", alert_data.rule_name)
        data.setdefault("tags", alert_data.tags or [])
        alert_id = str(alert_data.id)
    elif isinstance(alert_data, dict):
        data = alert_data
        alert_id = data.get("id", "")
    else:
        return {"triaged": False, "error": "Invalid alert data"}

    # Step 1: Extract IOCs
    iocs = await extract_phishing_iocs(data)

    # Step 2: Parallel enrichment — domain + IP reputation
    domain_intel, ip_intel = await asyncio.gather(
        check_domain_reputation(iocs["domains"]),
        check_ip_reputation(iocs["ips"] + ([iocs["dest_ip"]] if iocs["dest_ip"] else [])),
    )

    # Step 3: AI analysis
    ai_result = await ai_analyze_phishing(data, domain_intel, ip_intel)

    verdict = ai_result.get("verdict", "unknown")
    confidence = ai_result.get("confidence", 0.0)
    reasoning = ai_result.get("reasoning", "")

    # Step 4: Act on verdict
    if verdict == "benign" and confidence >= 0.85 and alert_id:
        resolution = await auto_resolve_benign(alert_id, reasoning)
    elif alert_id:
        resolution = await escalate_phishing(alert_id, verdict, reasoning)
    else:
        resolution = {"note": "No alert ID — dry run"}

    return {
        "triaged": True,
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": reasoning,
        "indicators": ai_result.get("indicators", []),
        "recommended_actions": ai_result.get("recommended_actions", []),
        "enrichment": {
            "domains": domain_intel,
            "ips": ip_intel,
        },
        "resolution": resolution,
        "model": ai_result.get("model"),
    }
