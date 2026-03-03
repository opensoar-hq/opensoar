from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.jwt import get_current_analyst
from opensoar.models.activity import Activity
from opensoar.models.analyst import Analyst
from opensoar.schemas.action import (
    ActionExecuteRequest,
    ActionExecuteResponse,
    AvailableAction,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])

# Registry of available manual actions per IOC type
AVAILABLE_ACTIONS: list[AvailableAction] = [
    AvailableAction(
        name="virustotal_lookup",
        integration="virustotal",
        description="Look up IP, domain, or hash on VirusTotal",
        ioc_types=["ips", "domains", "hashes"],
    ),
    AvailableAction(
        name="abuseipdb_check",
        integration="abuseipdb",
        description="Check IP reputation on AbuseIPDB",
        ioc_types=["ips"],
    ),
    AvailableAction(
        name="whois_lookup",
        integration="builtin",
        description="Perform WHOIS lookup on domain or IP",
        ioc_types=["ips", "domains"],
    ),
    AvailableAction(
        name="dns_resolve",
        integration="builtin",
        description="Resolve DNS records for a domain",
        ioc_types=["domains"],
    ),
]


@router.get("", response_model=list[AvailableAction])
async def list_available_actions(ioc_type: str | None = None):
    if ioc_type:
        return [a for a in AVAILABLE_ACTIONS if ioc_type in a.ioc_types]
    return AVAILABLE_ACTIONS


@router.post("/execute", response_model=ActionExecuteResponse)
async def execute_action(
    body: ActionExecuteRequest,
    session: AsyncSession = Depends(get_db),
    analyst: Analyst | None = Depends(get_current_analyst),
):
    action = next((a for a in AVAILABLE_ACTIONS if a.name == body.action_name), None)
    if not action:
        return ActionExecuteResponse(
            action_name=body.action_name,
            ioc_value=body.ioc_value,
            status="failed",
            error=f"Unknown action: {body.action_name}",
        )

    # Execute the action
    try:
        result = await _run_action(body.action_name, body.ioc_type, body.ioc_value)
        status = "success"
        error = None
    except Exception as e:
        logger.exception(f"Action {body.action_name} failed for {body.ioc_value}")
        result = None
        status = "failed"
        error = str(e)

    # Log activity if linked to an alert
    if body.alert_id:
        activity = Activity(
            alert_id=uuid.UUID(body.alert_id),
            analyst_id=analyst.id if analyst else None,
            analyst_username=analyst.username if analyst else None,
            action="manual_action",
            detail=f"Executed {body.action_name} on {body.ioc_type}: {body.ioc_value}",
            metadata_json={
                "action_name": body.action_name,
                "ioc_type": body.ioc_type,
                "ioc_value": body.ioc_value,
                "status": status,
                "result": result,
            },
        )
        session.add(activity)
        await session.commit()

    return ActionExecuteResponse(
        action_name=body.action_name,
        ioc_value=body.ioc_value,
        status=status,
        result=result,
        error=error,
    )


async def _run_action(action_name: str, ioc_type: str, ioc_value: str) -> dict:
    """Execute a manual enrichment action. Returns result dict."""
    import asyncio
    import socket

    if action_name == "whois_lookup":
        # Built-in WHOIS — run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        try:
            import whois as python_whois

            w = await loop.run_in_executor(None, python_whois.whois, ioc_value)
            return {
                "domain_name": w.domain_name,
                "registrar": w.registrar,
                "creation_date": str(w.creation_date),
                "expiration_date": str(w.expiration_date),
                "name_servers": w.name_servers,
                "org": w.org,
                "country": w.country,
            }
        except ImportError:
            return {"info": f"WHOIS lookup for {ioc_value} (python-whois not installed)"}
        except Exception as e:
            return {"info": f"WHOIS lookup for {ioc_value}", "error": str(e)}

    elif action_name == "dns_resolve":
        loop = asyncio.get_event_loop()
        try:
            addrs = await loop.run_in_executor(
                None, lambda: socket.getaddrinfo(ioc_value, None)
            )
            ips = list({addr[4][0] for addr in addrs})
            return {"domain": ioc_value, "resolved_ips": ips}
        except socket.gaierror:
            return {"domain": ioc_value, "resolved_ips": [], "error": "DNS resolution failed"}

    elif action_name == "virustotal_lookup":
        from opensoar.config import settings

        if not settings.vt_api_key:
            return {
                "source": "virustotal",
                "indicator": ioc_value,
                "note": "VirusTotal not configured. Add VT_API_KEY to .env.",
            }
        from opensoar.integrations.virustotal.connector import VirusTotalIntegration

        vt = VirusTotalIntegration({"api_key": settings.vt_api_key})
        await vt.connect()
        try:
            if ioc_type == "ips":
                raw = await vt.lookup_ip(ioc_value)
            elif ioc_type == "hashes":
                raw = await vt.lookup_hash(ioc_value)
            elif ioc_type == "domains":
                raw = await vt.lookup_domain(ioc_value)
            else:
                return {"error": f"Unsupported IOC type for VT: {ioc_type}"}
            # Extract summary from VT response
            data = raw.get("data", {}).get("attributes", {})
            stats = data.get("last_analysis_stats", {})
            return {
                "source": "virustotal",
                "indicator": ioc_value,
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "harmless": stats.get("harmless", 0),
                "undetected": stats.get("undetected", 0),
                "reputation": data.get("reputation"),
                "country": data.get("country"),
                "as_owner": data.get("as_owner"),
            }
        finally:
            await vt.disconnect()

    elif action_name == "abuseipdb_check":
        from opensoar.config import settings

        if not settings.abuseipdb_api_key:
            return {
                "source": "abuseipdb",
                "indicator": ioc_value,
                "note": "AbuseIPDB not configured. Add ABUSEIPDB_API_KEY to .env.",
            }
        from opensoar.integrations.abuseipdb.connector import AbuseIPDBIntegration

        abuse = AbuseIPDBIntegration({"api_key": settings.abuseipdb_api_key})
        await abuse.connect()
        try:
            raw = await abuse.check_ip(ioc_value)
            data = raw.get("data", {})
            return {
                "source": "abuseipdb",
                "indicator": ioc_value,
                "abuse_confidence_score": data.get("abuseConfidenceScore"),
                "total_reports": data.get("totalReports"),
                "country_code": data.get("countryCode"),
                "isp": data.get("isp"),
                "domain": data.get("domain"),
                "is_tor": data.get("isTor"),
                "is_whitelisted": data.get("isWhitelisted"),
            }
        finally:
            await abuse.disconnect()

    return {"action": action_name, "indicator": ioc_value, "note": "Action executed"}
