#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.28"]
# ///
"""Seed OpenSOAR with realistic demo data for a populated dashboard.

Usage:
    uv run scripts/seed.py                    # seed with defaults
    uv run scripts/seed.py --api-url http://myhost:8000
    uv run scripts/seed.py --clean            # remove seed data and re-seed
    uv run scripts/seed.py --clean --no-seed  # only remove seed data
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEED_TAG = "opensoar-seed"  # tag applied to all seed data for idempotency

DEMO_USER = {
    "username": "demo",
    "display_name": "Demo Analyst",
    "email": "demo@opensoar.app",
    "password": "demo123",
    "role": "admin",
}

# Realistic SHA-256 hashes (deterministic from known strings)
def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


ALERTS = [
    # ── CRITICAL ──────────────────────────────────────────────
    {
        "title": "Ransomware Binary Detected — LockBit 3.0 Variant",
        "description": (
            "CrowdStrike Falcon detected execution of a known LockBit 3.0 ransomware "
            "binary on WKSTN-FIN-042. The process attempted to enumerate network shares "
            "and encrypt files under C:\\Users. Execution was blocked by Falcon Prevent."
        ),
        "severity": "critical",
        "source": "crowdstrike",
        "source_ip": "10.20.5.42",
        "dest_ip": "10.20.5.1",
        "hostname": "WKSTN-FIN-042",
        "rule_name": "Ransomware Activity Detected",
        "tags": ["ransomware", "lockbit", "endpoint", "blocked"],
        "iocs": {
            "hashes": [_sha256("lockbit3_payload.exe"), _sha256("lockbit3_dropper.dll")],
            "ips": ["198.51.100.44", "203.0.113.87"],
            "domains": ["update-service-cdn.xyz", "dl.lockbit-decryptor.onion.ws"],
        },
        "status": "in_progress",
        "determination": "malicious",
        "hours_ago": 2,
    },
    {
        "title": "DNS Exfiltration — High Volume TXT Queries to Suspicious Domain",
        "description": (
            "Elastic SIEM detected anomalous DNS activity from SRV-DB-01. Over 4,200 TXT "
            "queries to subdomains of exfil.data-analytics-cdn.com in 15 minutes. Encoded "
            "payloads detected in query names, consistent with DNS tunneling."
        ),
        "severity": "critical",
        "source": "elastic",
        "source_ip": "10.10.3.15",
        "dest_ip": "198.51.100.53",
        "hostname": "SRV-DB-01",
        "rule_name": "DNS Exfiltration Detected",
        "tags": ["exfiltration", "dns-tunneling", "data-loss"],
        "iocs": {
            "domains": ["exfil.data-analytics-cdn.com", "c2.data-analytics-cdn.com"],
            "ips": ["198.51.100.53"],
        },
        "status": "in_progress",
        "determination": "malicious",
        "hours_ago": 1,
    },
    # ── HIGH ──────────────────────────────────────────────────
    {
        "title": "Lateral Movement — PsExec to Domain Controller",
        "description": (
            "Wazuh detected PsExec execution from WKSTN-IT-007 targeting the domain "
            "controller DC-PROD-01. The source account (svc_backup) is a service account "
            "not typically used for interactive sessions."
        ),
        "severity": "high",
        "source": "wazuh",
        "source_ip": "10.10.1.107",
        "dest_ip": "10.10.1.10",
        "hostname": "WKSTN-IT-007",
        "rule_name": "Lateral Movement via PsExec",
        "tags": ["lateral-movement", "psexec", "active-directory"],
        "iocs": {
            "ips": ["10.10.1.107", "10.10.1.10"],
            "hashes": [_sha256("psexesvc.exe")],
        },
        "status": "new",
        "determination": "unknown",
        "hours_ago": 3,
    },
    {
        "title": "Privilege Escalation — Token Impersonation via PrintSpoofer",
        "description": (
            "CrowdStrike detected PrintSpoofer.exe execution on SRV-WEB-03. The process "
            "escalated from IIS AppPool identity to NT AUTHORITY\\SYSTEM. This is a known "
            "privilege escalation technique (T1134.001)."
        ),
        "severity": "high",
        "source": "crowdstrike",
        "source_ip": "10.20.2.33",
        "hostname": "SRV-WEB-03",
        "rule_name": "Privilege Escalation — Token Impersonation",
        "tags": ["privilege-escalation", "T1134", "web-server"],
        "iocs": {
            "hashes": [_sha256("PrintSpoofer64.exe")],
        },
        "status": "new",
        "determination": "unknown",
        "hours_ago": 5,
    },
    {
        "title": "Phishing — User Clicked Credential Harvesting URL",
        "description": (
            "Elastic SIEM proxy logs show user j.martinez@corp.local clicked a link in email "
            "leading to login-microsft365.xyz/auth/signin. The domain was registered 2 days "
            "ago and mimics Microsoft 365 login. User entered credentials before IT was alerted."
        ),
        "severity": "high",
        "source": "elastic",
        "source_ip": "10.10.4.88",
        "dest_ip": "203.0.113.22",
        "hostname": "WKSTN-MKT-088",
        "rule_name": "Phishing URL Clicked — Credential Harvesting",
        "tags": ["phishing", "credential-harvest", "email"],
        "iocs": {
            "urls": ["https://login-microsft365.xyz/auth/signin"],
            "domains": ["login-microsft365.xyz"],
            "ips": ["203.0.113.22"],
        },
        "status": "in_progress",
        "determination": "malicious",
        "hours_ago": 6,
    },
    # ── MEDIUM ────────────────────────────────────────────────
    {
        "title": "SSH Brute Force — 847 Failed Attempts from Single IP",
        "description": (
            "Wazuh detected 847 failed SSH login attempts against SRV-JUMP-01 from "
            "198.51.100.14 over a 10-minute window. Targeted usernames include root, "
            "admin, ubuntu, deploy, and jenkins."
        ),
        "severity": "medium",
        "source": "wazuh",
        "source_ip": "198.51.100.14",
        "dest_ip": "10.10.1.50",
        "hostname": "SRV-JUMP-01",
        "rule_name": "SSH Brute Force Attack",
        "tags": ["brute-force", "ssh", "authentication"],
        "iocs": {
            "ips": ["198.51.100.14"],
        },
        "status": "resolved",
        "determination": "malicious",
        "resolve_reason": "Source IP blocked at firewall. No successful logins detected.",
        "hours_ago": 18,
    },
    {
        "title": "Suspicious PowerShell — Encoded Command with Network Activity",
        "description": (
            "Elastic SIEM detected PowerShell execution with Base64-encoded command on "
            "WKSTN-HR-015. Decoded payload contains Invoke-WebRequest to "
            "203.0.113.99/payload.ps1. Process spawned by winword.exe (possible macro execution)."
        ),
        "severity": "medium",
        "source": "elastic",
        "source_ip": "10.10.5.15",
        "dest_ip": "203.0.113.99",
        "hostname": "WKSTN-HR-015",
        "rule_name": "Suspicious PowerShell Execution",
        "tags": ["powershell", "encoded-command", "macro", "T1059.001"],
        "iocs": {
            "urls": ["http://203.0.113.99/payload.ps1"],
            "ips": ["203.0.113.99"],
            "hashes": [_sha256("encoded_ps1_stage2")],
        },
        "status": "new",
        "determination": "unknown",
        "hours_ago": 4,
    },
    {
        "title": "Port Scan Detected — Internal Host Scanning /24 Subnet",
        "description": (
            "Wazuh network IDS detected SRV-DEV-02 (10.10.6.20) performing a TCP SYN scan "
            "across 10.10.1.0/24 targeting ports 22, 80, 443, 445, 3389. 214 hosts contacted "
            "in 90 seconds."
        ),
        "severity": "medium",
        "source": "wazuh",
        "source_ip": "10.10.6.20",
        "hostname": "SRV-DEV-02",
        "rule_name": "Internal Network Port Scan",
        "tags": ["reconnaissance", "port-scan", "T1046"],
        "iocs": {
            "ips": ["10.10.6.20"],
        },
        "status": "in_progress",
        "determination": "suspicious",
        "hours_ago": 8,
    },
    {
        "title": "Failed Login Spike — 23 Failures for admin@corp.local in 5 Minutes",
        "description": (
            "Elastic SIEM detected 23 failed Active Directory login attempts for "
            "admin@corp.local from 4 different source IPs within a 5-minute window. "
            "This may indicate a password spraying attack against a high-value account."
        ),
        "severity": "medium",
        "source": "elastic",
        "source_ip": "198.51.100.71",
        "dest_ip": "10.10.1.10",
        "hostname": "DC-PROD-01",
        "rule_name": "Failed Login Spike — Possible Password Spray",
        "tags": ["password-spray", "authentication", "active-directory"],
        "iocs": {
            "ips": ["198.51.100.71", "198.51.100.72", "203.0.113.15", "203.0.113.16"],
        },
        "status": "new",
        "determination": "unknown",
        "hours_ago": 7,
    },
    {
        "title": "Impossible Travel — VPN Login from Two Countries in 30 Minutes",
        "description": (
            "Custom webhook detected VPN authentication for user d.chen@corp.local from "
            "Frankfurt, DE (198.51.100.200) at 14:02 UTC, followed by login from "
            "Singapore (203.0.113.180) at 14:28 UTC. Physical travel not possible in timeframe."
        ),
        "severity": "medium",
        "source": "webhook",
        "source_ip": "203.0.113.180",
        "dest_ip": "10.10.1.5",
        "hostname": "VPN-GW-01",
        "rule_name": "Impossible Travel Detected",
        "tags": ["impossible-travel", "vpn", "identity"],
        "iocs": {
            "ips": ["198.51.100.200", "203.0.113.180"],
        },
        "status": "resolved",
        "determination": "benign",
        "resolve_reason": "Confirmed with user — using corporate VPN exit node in Singapore.",
        "hours_ago": 12,
    },
    # ── LOW ───────────────────────────────────────────────────
    {
        "title": "Malware Detection — Adware PUP Quarantined on WKSTN-SALES-022",
        "description": (
            "CrowdStrike quarantined BrowserAssistant.exe (adware/PUP) on WKSTN-SALES-022. "
            "The file was downloaded from free-pdf-converter.com. No malicious C2 activity "
            "observed. Low-confidence threat."
        ),
        "severity": "low",
        "source": "crowdstrike",
        "source_ip": "10.10.7.22",
        "dest_ip": "203.0.113.150",
        "hostname": "WKSTN-SALES-022",
        "rule_name": "PUP/Adware Detected and Quarantined",
        "tags": ["malware", "adware", "pup", "quarantined"],
        "iocs": {
            "hashes": [_sha256("BrowserAssistant.exe")],
            "domains": ["free-pdf-converter.com"],
            "ips": ["203.0.113.150"],
        },
        "status": "resolved",
        "determination": "benign",
        "resolve_reason": "Adware quarantined automatically. User educated on safe downloads.",
        "hours_ago": 20,
    },
    {
        "title": "Outbound Connection to Tor Exit Node",
        "description": (
            "Elastic SIEM flagged an outbound TCP connection from WKSTN-ENG-009 to known "
            "Tor exit node 198.51.100.111 on port 9001. Single connection, no sustained activity."
        ),
        "severity": "low",
        "source": "elastic",
        "source_ip": "10.10.8.9",
        "dest_ip": "198.51.100.111",
        "hostname": "WKSTN-ENG-009",
        "rule_name": "Connection to Tor Exit Node",
        "tags": ["tor", "anonymization", "network"],
        "iocs": {
            "ips": ["198.51.100.111"],
        },
        "status": "resolved",
        "determination": "suspicious",
        "resolve_reason": "Engineer was testing Tor Browser for research. Reminded of acceptable use policy.",
        "hours_ago": 16,
    },
    {
        "title": "GPO Modification — New Logon Script Added",
        "description": (
            "Wazuh detected a Group Policy Object modification on DC-PROD-01. A new logon "
            "script (update_config.bat) was added to the Default Domain Policy by "
            "admin@corp.local. Change may be legitimate but requires verification."
        ),
        "severity": "low",
        "source": "wazuh",
        "source_ip": "10.10.1.10",
        "hostname": "DC-PROD-01",
        "rule_name": "GPO Modification Detected",
        "tags": ["gpo", "active-directory", "persistence"],
        "iocs": {},
        "status": "new",
        "determination": "unknown",
        "hours_ago": 10,
    },
    # ── INFO ──────────────────────────────────────────────────
    {
        "title": "New User Account Created — svc_monitoring",
        "description": (
            "Elastic SIEM audit log shows a new service account svc_monitoring was created "
            "in Active Directory by admin@corp.local. Account added to 'Read-Only Domain "
            "Controllers' group."
        ),
        "severity": "low",
        "source": "elastic",
        "source_ip": "10.10.1.10",
        "hostname": "DC-PROD-01",
        "rule_name": "New Service Account Created",
        "tags": ["account-creation", "active-directory", "audit"],
        "iocs": {},
        "status": "resolved",
        "determination": "benign",
        "resolve_reason": "Planned account creation per change request CR-2024-1847.",
        "hours_ago": 22,
    },
    {
        "title": "SSL Certificate Expiring — api.corp.local (7 Days)",
        "description": (
            "Custom webhook monitoring detected that the TLS certificate for api.corp.local "
            "expires in 7 days. Certificate issued by Let's Encrypt, auto-renewal may have "
            "failed."
        ),
        "severity": "low",
        "source": "webhook",
        "hostname": "SRV-API-01",
        "rule_name": "SSL Certificate Expiration Warning",
        "tags": ["certificate", "tls", "maintenance"],
        "iocs": {
            "domains": ["api.corp.local"],
        },
        "status": "new",
        "determination": "unknown",
        "hours_ago": 14,
    },
]

# Incidents that group related alerts together
INCIDENTS = [
    {
        "title": "Active Intrusion — Lateral Movement and Data Exfiltration",
        "description": (
            "Coordinated attack involving lateral movement via PsExec from WKSTN-IT-007 "
            "to DC-PROD-01, followed by DNS exfiltration from SRV-DB-01. Attacker appears "
            "to have compromised svc_backup service account. IR team engaged."
        ),
        "severity": "critical",
        "tags": ["active-intrusion", "ir-engaged"],
        # Indices into ALERTS list for linking
        "alert_indices": [1, 2],  # DNS exfil + lateral movement
    },
    {
        "title": "Phishing Campaign — Microsoft 365 Credential Harvesting",
        "description": (
            "Multiple users targeted by phishing emails impersonating Microsoft 365 login. "
            "At least one user (j.martinez) entered credentials. Password reset initiated, "
            "monitoring for follow-up account compromise."
        ),
        "severity": "high",
        "tags": ["phishing-campaign", "credential-compromise"],
        "alert_indices": [4, 8],  # Phishing + failed login spike
    },
]


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

class SeedClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.api = f"{self.base}/api/v1"
        self.client = httpx.Client(timeout=30)
        self.token: str | None = None

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    # ── Auth ──────────────────────────────────────────────────

    def register_or_login(self, user: dict) -> dict:
        """Register the demo user, or login if already exists."""
        resp = self.client.post(
            f"{self.api}/auth/register",
            json=user,
            headers=self._headers(),
        )
        if resp.status_code == 409:
            # Already exists — login instead
            resp = self.client.post(
                f"{self.api}/auth/login",
                json={"username": user["username"], "password": user["password"]},
                headers=self._headers(),
            )
        resp.raise_for_status()
        data = resp.json()
        self.token = data["access_token"]
        return data["analyst"]

    # ── Alerts ────────────────────────────────────────────────

    def check_seed_exists(self) -> bool:
        """Check if seed data already exists by looking for the seed tag."""
        resp = self.client.get(
            f"{self.api}/alerts",
            params={"limit": 1},
            headers=self._headers(),
        )
        resp.raise_for_status()
        alerts = resp.json()["alerts"]
        for a in alerts:
            if a.get("tags") and SEED_TAG in a["tags"]:
                return True
        # Also check with a bigger window
        resp = self.client.get(
            f"{self.api}/alerts",
            params={"limit": 200},
            headers=self._headers(),
        )
        resp.raise_for_status()
        for a in resp.json()["alerts"]:
            if a.get("tags") and SEED_TAG in a["tags"]:
                return True
        return False

    def ingest_alert(self, alert_data: dict) -> dict:
        """Ingest an alert via the webhook endpoint."""
        now = datetime.now(timezone.utc)
        hours_ago = alert_data.get("hours_ago", 0)
        jitter_minutes = random.randint(-15, 15)
        ts = now - timedelta(hours=hours_ago, minutes=jitter_minutes)

        # Build webhook payload that the normalizer will pick up
        payload = {
            "source_id": f"seed-{uuid.uuid4().hex[:12]}",
            "title": alert_data["title"],
            "description": alert_data["description"],
            "severity": alert_data["severity"],
            "source": alert_data["source"],
            "source_ip": alert_data.get("source_ip"),
            "dest_ip": alert_data.get("dest_ip"),
            "hostname": alert_data.get("hostname"),
            "rule_name": alert_data.get("rule_name"),
            "tags": alert_data.get("tags", []) + [SEED_TAG],
            "timestamp": ts.isoformat(),
        }
        # Add IOCs in a format the extract_iocs walker will find
        iocs = alert_data.get("iocs", {})
        if iocs.get("ips"):
            payload["ioc_ips"] = iocs["ips"]
            for i, ip in enumerate(iocs["ips"]):
                payload[f"indicator_ip_{i}"] = ip
        if iocs.get("domains"):
            payload["ioc_domains"] = iocs["domains"]
            for i, d in enumerate(iocs["domains"]):
                payload[f"indicator_domain_{i}"] = d
        if iocs.get("hashes"):
            payload["ioc_hashes"] = iocs["hashes"]
            for i, h in enumerate(iocs["hashes"]):
                payload[f"indicator_sha256_{i}"] = h
        if iocs.get("urls"):
            payload["ioc_urls"] = iocs["urls"]
            for i, u in enumerate(iocs["urls"]):
                payload[f"indicator_url_{i}"] = u

        resp = self.client.post(
            f"{self.api}/webhooks/alerts",
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def update_alert(self, alert_id: str, update: dict) -> dict:
        resp = self.client.patch(
            f"{self.api}/alerts/{alert_id}",
            json=update,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def get_alerts_by_tag(self, tag: str) -> list[dict]:
        """Fetch all alerts and filter by tag (API doesn't support tag filtering)."""
        resp = self.client.get(
            f"{self.api}/alerts",
            params={"limit": 200},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return [a for a in resp.json()["alerts"] if a.get("tags") and tag in a["tags"]]

    def delete_alert(self, alert_id: str) -> None:
        self.client.delete(
            f"{self.api}/alerts/{alert_id}",
            headers=self._headers(),
        )

    # ── Incidents ─────────────────────────────────────────────

    def create_incident(self, data: dict) -> dict:
        resp = self.client.post(
            f"{self.api}/incidents",
            json=data,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def link_alert_to_incident(self, incident_id: str, alert_id: str) -> None:
        resp = self.client.post(
            f"{self.api}/incidents/{incident_id}/alerts",
            json={"alert_id": alert_id},
            headers=self._headers(),
        )
        if resp.status_code == 409:
            return  # already linked
        resp.raise_for_status()

    def get_incidents_by_tag(self) -> list[dict]:
        """Fetch all incidents (no tag filter on API, so we check manually)."""
        resp = self.client.get(
            f"{self.api}/incidents",
            params={"limit": 200},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return [
            i for i in resp.json()["incidents"]
            if i.get("tags") and SEED_TAG in i["tags"]
        ]

    def delete_incident(self, incident_id: str) -> None:
        # No delete endpoint for incidents, so we close them
        # Actually try delete if it exists
        resp = self.client.delete(
            f"{self.api}/incidents/{incident_id}",
            headers=self._headers(),
        )
        # If no delete endpoint, just close it
        if resp.status_code in (404, 405):
            self.client.patch(
                f"{self.api}/incidents/{incident_id}",
                json={"status": "closed", "tags": []},
                headers=self._headers(),
            )


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

def clean(client: SeedClient) -> None:
    """Remove all seed data."""
    print("\n── Cleaning seed data ──")

    # Remove seed alerts
    alerts = client.get_alerts_by_tag(SEED_TAG)
    for a in alerts:
        client.delete_alert(a["id"])
        print(f"  Deleted alert: {a['title'][:60]}")

    # Remove seed incidents
    incidents = client.get_incidents_by_tag()
    for i in incidents:
        client.delete_incident(i["id"])
        print(f"  Deleted incident: {i['title'][:60]}")

    count = len(alerts) + len(incidents)
    if count == 0:
        print("  No seed data found.")
    else:
        print(f"  Removed {count} seed items.")


def seed(client: SeedClient) -> None:
    """Create all seed data."""
    print("\n── Creating demo analyst ──")
    analyst = client.register_or_login(DEMO_USER)
    analyst_id = analyst["id"]
    print(f"  Analyst: {analyst['username']} ({analyst['email']}) role={analyst['role']}")

    # Check idempotency
    if client.check_seed_exists():
        print("\n  Seed data already exists. Use --clean to remove and re-seed.")
        return

    print(f"\n── Ingesting {len(ALERTS)} alerts ──")
    created_alerts: list[dict] = []
    for i, alert_def in enumerate(ALERTS, 1):
        result = client.ingest_alert(alert_def)
        alert_id = result["alert_id"]
        print(f"  [{i:2d}/{len(ALERTS)}] {alert_def['severity']:8s} | {alert_def['title'][:65]}")
        created_alerts.append({"id": str(alert_id), **alert_def})

    # Apply statuses, determinations, and assignments
    print("\n── Updating alert statuses ──")
    for i, alert_def in enumerate(ALERTS):
        alert_id = created_alerts[i]["id"]
        update: dict = {}

        if alert_def.get("determination", "unknown") != "unknown":
            update["determination"] = alert_def["determination"]

        if alert_def["status"] == "in_progress":
            update["status"] = "in_progress"
            update["assigned_to"] = analyst_id
        elif alert_def["status"] == "resolved":
            # Must set determination before resolving
            if update.get("determination"):
                client.update_alert(alert_id, {"determination": update.pop("determination")})
            else:
                client.update_alert(alert_id, {"determination": "benign"})
            update["status"] = "resolved"
            if alert_def.get("resolve_reason"):
                update["resolve_reason"] = alert_def["resolve_reason"]

        if update:
            client.update_alert(alert_id, update)
            print(f"  Updated: {alert_def['title'][:55]} -> {alert_def['status']}")

    # Create incidents
    print(f"\n── Creating {len(INCIDENTS)} incidents ──")
    for inc_def in INCIDENTS:
        incident = client.create_incident({
            "title": inc_def["title"],
            "description": inc_def["description"],
            "severity": inc_def["severity"],
            "tags": inc_def.get("tags", []) + [SEED_TAG],
        })
        inc_id = incident["id"]
        print(f"  Incident: {inc_def['title'][:65]}")

        # Link related alerts
        for idx in inc_def["alert_indices"]:
            if idx < len(created_alerts):
                client.link_alert_to_incident(inc_id, created_alerts[idx]["id"])
                print(f"    Linked: {ALERTS[idx]['title'][:55]}")

    # Summary
    print("\n── Seed complete ──")
    status_counts = {}
    sev_counts = {}
    source_counts = {}
    for a in ALERTS:
        status_counts[a["status"]] = status_counts.get(a["status"], 0) + 1
        sev_counts[a["severity"]] = sev_counts.get(a["severity"], 0) + 1
        source_counts[a["source"]] = source_counts.get(a["source"], 0) + 1

    print(f"  Alerts:    {len(ALERTS)}")
    print(f"  Incidents: {len(INCIDENTS)}")
    print(f"  Severities: {dict(sorted(sev_counts.items()))}")
    print(f"  Statuses:   {dict(sorted(status_counts.items()))}")
    print(f"  Sources:    {dict(sorted(source_counts.items()))}")
    print(f"\n  Login:  demo / demo123")
    print(f"  URL:    {client.base}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed OpenSOAR with demo data")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="OpenSOAR API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing seed data before seeding",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Only clean, do not re-seed (use with --clean)",
    )
    args = parser.parse_args()

    print(f"OpenSOAR Seed — targeting {args.api_url}")

    # Check API is reachable
    try:
        resp = httpx.get(f"{args.api_url}/api/v1/health", timeout=5)
        resp.raise_for_status()
        print("API is healthy.")
    except Exception:
        print(f"ERROR: Cannot reach API at {args.api_url}/api/v1/health")
        print("Make sure OpenSOAR is running (docker compose up -d)")
        sys.exit(1)

    client = SeedClient(args.api_url)

    # Always register/login first so we have auth
    client.register_or_login(DEMO_USER)

    if args.clean:
        clean(client)

    if not args.no_seed:
        seed(client)


if __name__ == "__main__":
    main()
