"""Playbook: Auto-enrich all IOCs in an alert.

Runs VirusTotal and AbuseIPDB lookups on every IP, domain, and hash
found in the alert's IOCs. Results are logged as activity entries.
"""

import asyncio
import logging

from opensoar import action, playbook

logger = logging.getLogger(__name__)


@action(name="enrich_ip", timeout=30, retries=2, retry_backoff=2.0)
async def enrich_ip(ip: str) -> dict:
    """Enrich a single IP address with VT + AbuseIPDB."""
    results = {"ip": ip, "sources": {}}

    try:
        from opensoar.config import settings

        if settings.vt_api_key:
            from opensoar.integrations.virustotal.connector import VirusTotalIntegration

            vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
            await vt.connect()
            try:
                raw = await vt.lookup_ip(ip)
                attrs = raw.get("data", {}).get("attributes", {})
                stats = attrs.get("last_analysis_stats", {})
                results["sources"]["virustotal"] = {
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
                raw = await abuse.check_ip(ip)
                data = raw.get("data", {})
                results["sources"]["abuseipdb"] = {
                    "abuse_confidence_score": data.get("abuseConfidenceScore"),
                    "total_reports": data.get("totalReports"),
                    "country_code": data.get("countryCode"),
                    "isp": data.get("isp"),
                }
            finally:
                await abuse.disconnect()
    except Exception as e:
        results["error"] = str(e)
        logger.warning(f"Enrichment failed for IP {ip}: {e}")

    if not results["sources"]:
        results["note"] = "No integration API keys configured"

    return results


@action(name="enrich_domain", timeout=30, retries=2, retry_backoff=2.0)
async def enrich_domain(domain: str) -> dict:
    """Enrich a domain with VirusTotal."""
    try:
        from opensoar.config import settings

        if not settings.vt_api_key:
            return {"domain": domain, "note": "VT_API_KEY not configured"}

        from opensoar.integrations.virustotal.connector import VirusTotalIntegration

        vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
        await vt.connect()
        try:
            raw = await vt.lookup_domain(domain)
            attrs = raw.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            return {
                "domain": domain,
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "registrar": attrs.get("registrar"),
                "creation_date": str(attrs.get("creation_date", "")),
            }
        finally:
            await vt.disconnect()
    except Exception as e:
        return {"domain": domain, "error": str(e)}


@action(name="enrich_hash", timeout=30, retries=2, retry_backoff=2.0)
async def enrich_hash(file_hash: str) -> dict:
    """Enrich a file hash with VirusTotal."""
    try:
        from opensoar.config import settings

        if not settings.vt_api_key:
            return {"hash": file_hash, "note": "VT_API_KEY not configured"}

        from opensoar.integrations.virustotal.connector import VirusTotalIntegration

        vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
        await vt.connect()
        try:
            raw = await vt.lookup_hash(file_hash)
            attrs = raw.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            return {
                "hash": file_hash,
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "type_description": attrs.get("type_description"),
                "meaningful_name": attrs.get("meaningful_name"),
            }
        finally:
            await vt.disconnect()
    except Exception as e:
        return {"hash": file_hash, "error": str(e)}


@playbook(
    trigger="webhook",
    conditions={},
    description="Auto-enrich all IOCs (IPs, domains, hashes) using configured integrations",
)
async def auto_enrich_iocs(alert_data):
    """Enrich every IOC found in the alert."""
    if hasattr(alert_data, "iocs"):
        iocs = alert_data.iocs or {}
    elif isinstance(alert_data, dict):
        iocs = alert_data.get("iocs", {})
    else:
        iocs = {}

    tasks = []
    for ip in iocs.get("ips", []):
        tasks.append(enrich_ip(ip))
    for domain in iocs.get("domains", []):
        tasks.append(enrich_domain(domain))
    for h in iocs.get("hashes", []):
        tasks.append(enrich_hash(h))

    if not tasks:
        return {"enriched": 0, "note": "No IOCs to enrich"}

    results = await asyncio.gather(*tasks, return_exceptions=True)

    enrichment = []
    for r in results:
        if isinstance(r, Exception):
            enrichment.append({"error": str(r)})
        else:
            enrichment.append(r)

    return {"enriched": len(enrichment), "results": enrichment}
