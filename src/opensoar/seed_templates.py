"""Built-in incident templates shipped with OpenSOAR.

These seed values are written into the database by the Alembic migration
``b8f3d2c1a9e7_add_incident_templates`` so fresh installs have starter
coverage for the three most common incident classes.  Exposed as plain
Python so tests and the UI can introspect the same source of truth.
"""
from __future__ import annotations

from typing import Any

SEED_INCIDENT_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Phishing",
        "description": "Email-based credential harvest or malware delivery.",
        "default_severity": "high",
        "default_tags": ["phishing", "email"],
        "playbook_ids": [],
        "observable_types": ["email", "url", "domain", "hash"],
    },
    {
        "name": "Ransomware",
        "description": "Encryption-based destructive attack on endpoints or file shares.",
        "default_severity": "critical",
        "default_tags": ["ransomware", "malware", "destructive"],
        "playbook_ids": [],
        "observable_types": ["hash", "ip", "domain", "hostname"],
    },
    {
        "name": "Data Exfiltration",
        "description": "Unauthorized outbound transfer of sensitive data.",
        "default_severity": "high",
        "default_tags": ["data-exfil", "insider-threat", "dlp"],
        "playbook_ids": [],
        "observable_types": ["ip", "domain", "url", "hostname"],
    },
]
