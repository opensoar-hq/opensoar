"""Playbook: AI-powered threat hunt.

Receives an IOC-bearing alert, searches across all configured integrations
(VirusTotal, AbuseIPDB) for correlated intelligence, then uses an LLM to
correlate findings and produce an analyst-ready threat hunt summary report.
"""

import asyncio
import json
import logging

from opensoar import action, playbook

logger = logging.getLogger(__name__)


@action(name="collect_hunt_iocs", timeout=10)
async def collect_hunt_iocs(alert_data: dict) -> dict:
    """Collect all IOCs from the alert for the threat hunt."""
    iocs = alert_data.get("iocs", {})
    all_ips = list(set(
        iocs.get("ips", [])
        + ([alert_data["source_ip"]] if alert_data.get("source_ip") else [])
        + ([alert_data["dest_ip"]] if alert_data.get("dest_ip") else [])
    ))
    return {
        "ips": all_ips,
        "domains": iocs.get("domains", []),
        "hashes": iocs.get("hashes", []),
        "urls": iocs.get("urls", []),
        "hostname": alert_data.get("hostname"),
        "total_iocs": len(all_ips) + len(iocs.get("domains", [])) + len(iocs.get("hashes", [])),
    }


@action(name="hunt_ips", timeout=45, retries=2, retry_backoff=2.0)
async def hunt_ips(ips: list[str]) -> dict:
    """Search IPs across VirusTotal and AbuseIPDB."""
    results = {}
    for ip in ips[:10]:
        results[ip] = {"sources": {}}

    try:
        from opensoar.config import settings

        if settings.vt_api_key:
            from opensoar.integrations.virustotal.connector import VirusTotalIntegration

            vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
            await vt.connect()
            try:
                for ip in ips[:10]:
                    raw = await vt.lookup_ip(ip)
                    attrs = raw.get("data", {}).get("attributes", {})
                    stats = attrs.get("last_analysis_stats", {})
                    results[ip]["sources"]["virustotal"] = {
                        "malicious": stats.get("malicious", 0),
                        "suspicious": stats.get("suspicious", 0),
                        "country": attrs.get("country"),
                        "as_owner": attrs.get("as_owner"),
                    }
            finally:
                await vt.disconnect()

        if settings.abuseipdb_api_key:
            from opensoar.integrations.abuseipdb.connector import AbuseIPDBIntegration

            abuse = AbuseIPDBIntegration({"api_key": settings.abuseipdb_api_key})
            await abuse.connect()
            try:
                for ip in ips[:10]:
                    raw = await abuse.check_ip(ip)
                    data = raw.get("data", {})
                    results[ip]["sources"]["abuseipdb"] = {
                        "abuse_confidence_score": data.get("abuseConfidenceScore", 0),
                        "total_reports": data.get("totalReports", 0),
                        "country_code": data.get("countryCode"),
                        "isp": data.get("isp"),
                    }
            finally:
                await abuse.disconnect()
    except Exception as e:
        logger.warning(f"IP hunt enrichment failed: {e}")

    return {"type": "ip", "results": results}


@action(name="hunt_domains", timeout=45, retries=2, retry_backoff=2.0)
async def hunt_domains(domains: list[str]) -> dict:
    """Search domains via VirusTotal."""
    results = {}
    try:
        from opensoar.config import settings

        if settings.vt_api_key:
            from opensoar.integrations.virustotal.connector import VirusTotalIntegration

            vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
            await vt.connect()
            try:
                for domain in domains[:10]:
                    raw = await vt.lookup_domain(domain)
                    attrs = raw.get("data", {}).get("attributes", {})
                    stats = attrs.get("last_analysis_stats", {})
                    results[domain] = {
                        "malicious": stats.get("malicious", 0),
                        "suspicious": stats.get("suspicious", 0),
                        "registrar": attrs.get("registrar"),
                        "creation_date": str(attrs.get("creation_date", "")),
                        "categories": attrs.get("categories", {}),
                    }
            finally:
                await vt.disconnect()
        else:
            for domain in domains:
                results[domain] = {"note": "VT not configured"}
    except Exception as e:
        logger.warning(f"Domain hunt enrichment failed: {e}")

    return {"type": "domain", "results": results}


@action(name="hunt_hashes", timeout=45, retries=2, retry_backoff=2.0)
async def hunt_hashes(hashes: list[str]) -> dict:
    """Search file hashes via VirusTotal."""
    results = {}
    try:
        from opensoar.config import settings

        if settings.vt_api_key:
            from opensoar.integrations.virustotal.connector import VirusTotalIntegration

            vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
            await vt.connect()
            try:
                for file_hash in hashes[:10]:
                    raw = await vt.lookup_hash(file_hash)
                    attrs = raw.get("data", {}).get("attributes", {})
                    stats = attrs.get("last_analysis_stats", {})
                    results[file_hash] = {
                        "malicious": stats.get("malicious", 0),
                        "suspicious": stats.get("suspicious", 0),
                        "type_description": attrs.get("type_description"),
                        "meaningful_name": attrs.get("meaningful_name"),
                        "popular_threat_label": attrs.get("popular_threat_label"),
                        "first_submission_date": str(attrs.get("first_submission_date", "")),
                    }
            finally:
                await vt.disconnect()
        else:
            for h in hashes:
                results[h] = {"note": "VT not configured"}
    except Exception as e:
        logger.warning(f"Hash hunt enrichment failed: {e}")

    return {"type": "hash", "results": results}


@action(name="ai_correlate_and_report", timeout=90, retries=1)
async def ai_correlate_and_report(
    alert_data: dict, hunt_iocs: dict, ip_intel: dict, domain_intel: dict, hash_intel: dict
) -> dict:
    """Use an LLM to correlate all findings and write a threat hunt summary report."""
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
            "report": "No LLM configured — manual correlation required.",
            "threat_level": "unknown",
            "confidence": 0.0,
            "related_threats": [],
        }

    prompt = f"""Correlate the following threat hunt findings and write a concise analyst report.

ORIGINAL ALERT:
- Title: {alert_data.get("title", "N/A")}
- Description: {alert_data.get("description", "N/A")}
- Severity: {alert_data.get("severity", "N/A")}
- Source: {alert_data.get("source", "N/A")}
- Hostname: {alert_data.get("hostname", "N/A")}
- Rule: {alert_data.get("rule_name", "N/A")}
- Tags: {json.dumps(alert_data.get("tags", []))}

IOCs INVESTIGATED ({hunt_iocs.get("total_iocs", 0)} total):
- IPs: {json.dumps(hunt_iocs.get("ips", []))}
- Domains: {json.dumps(hunt_iocs.get("domains", []))}
- Hashes: {json.dumps(hunt_iocs.get("hashes", []))}

IP INTELLIGENCE:
{json.dumps(ip_intel.get("results", {}), indent=2)}

DOMAIN INTELLIGENCE:
{json.dumps(domain_intel.get("results", {}), indent=2)}

FILE HASH INTELLIGENCE:
{json.dumps(hash_intel.get("results", {}), indent=2)}

Respond with ONLY a JSON object:
{{
    "threat_level": "critical" | "high" | "medium" | "low" | "informational",
    "confidence": 0.0-1.0,
    "executive_summary": "2-3 sentence high-level summary for management",
    "report": "Detailed markdown threat hunt report (4-8 paragraphs) covering:\\n- Attack narrative and timeline\\n- IOC analysis and correlation\\n- Affected systems and scope\\n- Threat actor assessment (if determinable)\\n- Recommended response actions\\n- Detection gaps identified",
    "related_threats": ["list of related threat names, malware families, or APT groups"],
    "ioc_verdicts": {{
        "malicious": ["list of confirmed malicious IOCs"],
        "suspicious": ["list of suspicious IOCs"],
        "clean": ["list of clean IOCs"]
    }},
    "recommended_actions": ["prioritized list of next steps"]
}}"""

    response = await client.complete(
        prompt,
        system=(
            "You are a senior threat intelligence analyst writing a threat hunt report. "
            "Correlate IOC intelligence across all sources, identify attack patterns and "
            "threat actor TTPs (MITRE ATT&CK). Be thorough but concise. Your report will "
            "be read by SOC analysts and incident responders who need actionable intelligence."
        ),
        max_tokens=2048,
        temperature=0.2,
    )

    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        result = {
            "report": response.content[:2000],
            "threat_level": "unknown",
            "confidence": 0.5,
            "recommended_actions": ["Manual review required — LLM response was not structured"],
        }

    result["model"] = response.model
    return result


@action(name="save_hunt_report", timeout=15)
async def save_hunt_report(alert_id: str, report: dict) -> dict:
    """Save the threat hunt report as an activity on the alert."""
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
            return {"saved": False, "error": "Alert not found"}

        if alert.status == "new":
            alert.status = "in_progress"

        session.add(Activity(
            alert_id=alert.id,
            action="ai_threat_hunt_report",
            detail=report.get("executive_summary", "AI threat hunt completed"),
            metadata_json={
                "threat_level": report.get("threat_level"),
                "confidence": report.get("confidence"),
                "report": report.get("report"),
                "ioc_verdicts": report.get("ioc_verdicts", {}),
                "related_threats": report.get("related_threats", []),
                "recommended_actions": report.get("recommended_actions", []),
                "playbook": "ai_threat_hunt",
            },
        ))

        await session.commit()
        return {"saved": True, "threat_level": report.get("threat_level")}


@playbook(
    trigger="webhook",
    conditions={},
    description=(
        "AI-powered threat hunt: collect IOCs, search across all integrations, "
        "use LLM to correlate findings and produce a threat hunt summary report"
    ),
)
async def ai_threat_hunt(alert_data):
    """AI-powered threat hunt with cross-integration correlation and LLM report."""
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
        return {"hunted": False, "error": "Invalid alert data"}

    # Step 1: Collect all IOCs for the hunt
    hunt_iocs = await collect_hunt_iocs(data)

    if hunt_iocs["total_iocs"] == 0:
        return {"hunted": False, "note": "No IOCs to hunt — alert has no indicators"}

    # Step 2: Parallel enrichment across all integrations
    ip_intel, domain_intel, hash_intel = await asyncio.gather(
        hunt_ips(hunt_iocs["ips"]),
        hunt_domains(hunt_iocs["domains"]),
        hunt_hashes(hunt_iocs["hashes"]),
    )

    # Step 3: AI correlation and report generation
    report = await ai_correlate_and_report(
        data, hunt_iocs, ip_intel, domain_intel, hash_intel
    )

    # Step 4: Save report to alert
    if alert_id:
        save_result = await save_hunt_report(alert_id, report)
    else:
        save_result = {"note": "No alert ID — dry run"}

    return {
        "hunted": True,
        "threat_level": report.get("threat_level", "unknown"),
        "confidence": report.get("confidence", 0.0),
        "executive_summary": report.get("executive_summary", ""),
        "report": report.get("report", ""),
        "related_threats": report.get("related_threats", []),
        "ioc_verdicts": report.get("ioc_verdicts", {}),
        "recommended_actions": report.get("recommended_actions", []),
        "iocs_investigated": hunt_iocs["total_iocs"],
        "enrichment": {
            "ips": ip_intel,
            "domains": domain_intel,
            "hashes": hash_intel,
        },
        "saved": save_result,
        "model": report.get("model"),
    }
