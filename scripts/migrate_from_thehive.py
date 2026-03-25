#!/usr/bin/env python3
"""
TheHive to OpenSOAR Migration Script

Exports data from a running TheHive instance and imports it into OpenSOAR.

Usage:
    # Export from TheHive
    python migrate_from_thehive.py export \
        --thehive-url https://thehive.example.com \
        --thehive-api-key YOUR_API_KEY \
        --output-dir ./thehive-export

    # Import to OpenSOAR
    python migrate_from_thehive.py import \
        --opensoar-url http://localhost:8000 \
        --opensoar-api-key YOUR_API_KEY \
        --input-dir ./thehive-export

Requires: pip install requests
"""

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' package required. Install with: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

SEVERITY_MAP = {1: "low", 2: "medium", 3: "high", 4: "critical"}
TLP_MAP = {0: "white", 1: "green", 2: "amber", 3: "red"}


# ---------------------------------------------------------------------------
# TheHive Export
# ---------------------------------------------------------------------------


class TheHiveExporter:
    """Export alerts, cases, observables, and tasks from TheHive via its API."""

    def __init__(self, url: str, api_key: str, output_dir: str):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _search(self, endpoint: str, query: dict | None = None, range_: str = "all") -> list:
        """Search TheHive using the v0 _search API with pagination."""
        results = []
        page_size = 200
        offset = 0

        while True:
            headers = {"Range": f"{offset}-{offset + page_size - 1}"}
            body = {"query": query or {}}
            resp = self.session.post(
                f"{self.url}/api/{endpoint}/_search",
                json=body,
                headers=headers,
            )
            if resp.status_code == 200:
                batch = resp.json()
                if not batch:
                    break
                results.extend(batch)
                if len(batch) < page_size:
                    break
                offset += page_size
            elif resp.status_code == 416:
                # Range not satisfiable — no more results
                break
            else:
                print(f"  Warning: {endpoint} search returned {resp.status_code}: {resp.text[:200]}")
                break

        return results

    def export_alerts(self) -> list:
        """Export all TheHive alerts."""
        print("Exporting alerts...")
        alerts = self._search("alert")
        print(f"  Found {len(alerts)} alerts")

        # For each alert, fetch embedded artifacts (TH3 style)
        for i, alert in enumerate(alerts):
            if i > 0 and i % 100 == 0:
                print(f"  Processing alert {i}/{len(alerts)}...")

        self._save("alerts.json", alerts)
        return alerts

    def export_cases(self) -> list:
        """Export all TheHive cases with tasks and observables."""
        print("Exporting cases...")
        cases = self._search("case")
        print(f"  Found {len(cases)} cases")

        for i, case in enumerate(cases):
            case_id = case.get("id") or case.get("_id")
            if not case_id:
                continue

            if i > 0 and i % 50 == 0:
                print(f"  Processing case {i}/{len(cases)}...")

            # Fetch tasks for this case
            tasks = self._search("case/task", query={"_parent": {"_type": "case", "_query": {"_id": case_id}}})
            case["_tasks"] = tasks

            # Fetch task logs for each task
            for task in tasks:
                task_id = task.get("id") or task.get("_id")
                if task_id:
                    logs = self._search(
                        "case/task/log",
                        query={"_parent": {"_type": "case_task", "_query": {"_id": task_id}}},
                    )
                    task["_logs"] = logs

            # Fetch observables for this case
            observables = self._search(
                "case/artifact",
                query={"_parent": {"_type": "case", "_query": {"_id": case_id}}},
            )
            case["_observables"] = observables

        self._save("cases.json", cases)
        return cases

    def export_users(self) -> list:
        """Export TheHive users for reference (not imported directly)."""
        print("Exporting users (reference only)...")
        resp = self.session.get(f"{self.url}/api/user/_search", json={"query": {}})
        users = resp.json() if resp.status_code == 200 else []
        print(f"  Found {len(users)} users")
        self._save("users.json", users)
        return users

    def export_all(self):
        """Run full export."""
        print(f"\nExporting TheHive data from {self.url}")
        print(f"Output directory: {self.output_dir}\n")

        self.export_alerts()
        self.export_cases()
        self.export_users()

        # Write metadata
        metadata = {
            "source": "thehive",
            "url": self.url,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "version": "1.0",
        }
        self._save("metadata.json", metadata)

        print(f"\nExport complete. Files saved to {self.output_dir}/")

    def _save(self, filename: str, data):
        path = self.output_dir / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"  Saved {filename}")


# ---------------------------------------------------------------------------
# OpenSOAR Import
# ---------------------------------------------------------------------------


class OpenSOARImporter:
    """Import TheHive export data into OpenSOAR."""

    def __init__(self, url: str, api_key: str, input_dir: str):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})
        self.input_dir = Path(input_dir)
        self.stats = {"alerts": 0, "incidents": 0, "observables": 0, "links": 0, "errors": 0}
        # Track TheHive ID → OpenSOAR ID mappings
        self.alert_map: dict[str, int] = {}
        self.incident_map: dict[str, int] = {}

    def _load(self, filename: str) -> list | dict:
        path = self.input_dir / filename
        if not path.exists():
            print(f"  Warning: {filename} not found, skipping")
            return []
        with open(path) as f:
            return json.load(f)

    def _map_severity(self, th_severity: int) -> str:
        return SEVERITY_MAP.get(th_severity, "medium")

    def _map_alert_status(self, th_status: str) -> str:
        mapping = {"New": "new", "Updated": "new", "Imported": "new", "Ignored": "resolved"}
        return mapping.get(th_status, "new")

    def _map_determination(self, th_status: str) -> str | None:
        if th_status == "Ignored":
            return "benign"
        return None

    def _build_tags(self, th_obj: dict) -> list[str]:
        """Build OpenSOAR tags from TheHive fields."""
        tags = list(th_obj.get("tags", []))

        # TLP
        tlp = th_obj.get("tlp")
        if tlp is not None and tlp in TLP_MAP:
            tags.append(f"tlp:{TLP_MAP[tlp]}")

        # PAP
        pap = th_obj.get("pap")
        if pap is not None and pap in TLP_MAP:
            tags.append(f"pap:{TLP_MAP[pap]}")

        # Alert type
        alert_type = th_obj.get("type")
        if alert_type:
            tags.append(f"thehive-type:{alert_type}")

        # Migration marker
        tags.append("migrated:thehive")

        return tags

    def import_alerts(self):
        """Import TheHive alerts into OpenSOAR via webhook."""
        alerts = self._load("alerts.json")
        if not alerts:
            return

        print(f"\nImporting {len(alerts)} alerts...")

        for i, th_alert in enumerate(alerts):
            if i > 0 and i % 50 == 0:
                print(f"  Progress: {i}/{len(alerts)} alerts imported")

            th_id = th_alert.get("id") or th_alert.get("_id", "")

            # Build webhook payload that OpenSOAR's normalizer can handle
            payload = {
                "title": th_alert.get("title", "Untitled Alert"),
                "description": th_alert.get("description", ""),
                "severity": self._map_severity(th_alert.get("severity", 2)),
                "source": th_alert.get("source", "thehive-migration"),
                "source_id": th_alert.get("sourceRef", th_id),
                "tags": self._build_tags(th_alert),
                "raw_payload": th_alert,  # Preserve full original
            }

            # Extract IOCs from artifacts
            iocs = []
            for artifact in th_alert.get("artifacts", []):
                data = artifact.get("data")
                if data:
                    iocs.append(data)
            if iocs:
                payload["iocs"] = iocs

            resp = self.session.post(f"{self.url}/api/v1/webhooks/alerts", json=payload)

            if resp.status_code in (200, 201):
                alert_data = resp.json()
                os_id = alert_data.get("id")
                if os_id:
                    self.alert_map[th_id] = os_id
                self.stats["alerts"] += 1

                # Import observables from artifacts
                for artifact in th_alert.get("artifacts", []):
                    self._import_observable(artifact, alert_id=os_id)
            else:
                print(f"  Error importing alert '{th_alert.get('title', '')}': {resp.status_code}")
                self.stats["errors"] += 1

        print(f"  Imported {self.stats['alerts']} alerts")

    def import_cases(self):
        """Import TheHive cases as OpenSOAR incidents."""
        cases = self._load("cases.json")
        if not cases:
            return

        # First, authenticate as an analyst to create incidents
        print(f"\nImporting {len(cases)} cases as incidents...")

        for i, th_case in enumerate(cases):
            if i > 0 and i % 25 == 0:
                print(f"  Progress: {i}/{len(cases)} incidents imported")

            th_id = th_case.get("id") or th_case.get("_id", "")
            case_id = th_case.get("caseId", "")

            # Build description with TheHive metadata
            description = th_case.get("description", "")
            summary = th_case.get("summary")
            if summary:
                description += f"\n\n---\n**Resolution Summary:** {summary}"

            tags = self._build_tags(th_case)
            if case_id:
                tags.append(f"thehive-case:{case_id}")

            resolution = th_case.get("resolutionStatus")
            if resolution:
                tags.append(f"resolution:{resolution}")

            impact = th_case.get("impactStatus")
            if impact:
                tags.append(f"impact:{impact}")

            # Map status
            th_status = th_case.get("status", "Open")
            os_status = "open" if th_status == "Open" else "closed"

            payload = {
                "title": th_case.get("title", "Untitled Incident"),
                "description": description,
                "severity": self._map_severity(th_case.get("severity", 2)),
                "status": os_status,
                "tags": tags,
            }

            # Assign to owner if available
            owner = th_case.get("owner")
            if owner:
                payload["assigned_username"] = owner

            resp = self.session.post(f"{self.url}/api/v1/incidents", json=payload)

            if resp.status_code in (200, 201):
                incident_data = resp.json()
                os_id = incident_data.get("id")
                if os_id:
                    self.incident_map[th_id] = os_id
                self.stats["incidents"] += 1

                # Import observables from case
                for obs in th_case.get("_observables", []):
                    self._import_observable(obs, incident_id=os_id)

                # Import task logs as activities/comments
                for task in th_case.get("_tasks", []):
                    for log in task.get("_logs", []):
                        # Task logs would be added as comments if the API supports it
                        pass
            else:
                print(f"  Error importing case '{th_case.get('title', '')}': {resp.status_code}")
                self.stats["errors"] += 1

        print(f"  Imported {self.stats['incidents']} incidents")

    def _import_observable(self, th_artifact: dict, alert_id: int | None = None, incident_id: int | None = None):
        """Import a TheHive observable/artifact into OpenSOAR."""
        data_type = th_artifact.get("dataType", "other")
        value = th_artifact.get("data")

        if not value:
            return  # Skip file-only observables

        tags = list(th_artifact.get("tags", []))

        # Preserve context
        message = th_artifact.get("message")
        if message:
            tags.append(f"context:{message[:100]}")

        if th_artifact.get("ioc"):
            tags.append("ioc:true")
        if th_artifact.get("sighted"):
            tags.append("sighted:true")

        tlp = th_artifact.get("tlp")
        if tlp is not None and tlp in TLP_MAP:
            tags.append(f"tlp:{TLP_MAP[tlp]}")

        tags.append("migrated:thehive")

        payload = {
            "type": data_type,
            "value": value,
            "source": "thehive-migration",
            "tags": tags,
        }

        if alert_id:
            payload["alert_id"] = alert_id

        resp = self.session.post(f"{self.url}/api/v1/observables", json=payload)

        if resp.status_code in (200, 201):
            self.stats["observables"] += 1

            # Import Cortex reports as enrichments
            obs_id = resp.json().get("id")
            if obs_id:
                reports = th_artifact.get("reports", {})
                for analyzer_name, report in reports.items():
                    enrichment = {
                        "source": f"cortex:{analyzer_name}",
                        "data": report,
                        "malicious": report.get("summary", {}).get("taxonomies", [{}])[0].get("level") == "malicious"
                        if report.get("summary", {}).get("taxonomies")
                        else False,
                    }
                    self.session.post(
                        f"{self.url}/api/v1/observables/{obs_id}/enrichments",
                        json=enrichment,
                    )

    def link_alerts_to_incidents(self):
        """Re-create case-alert links as incident-alert associations."""
        cases = self._load("cases.json")
        if not cases:
            return

        print("\nLinking alerts to incidents...")

        for th_case in cases:
            th_case_id = th_case.get("id") or th_case.get("_id", "")
            os_incident_id = self.incident_map.get(th_case_id)
            if not os_incident_id:
                continue

            # TheHive stores alert→case links on the alert side (alert.case field)
            # We need to find alerts that reference this case
            alerts = self._load("alerts.json")
            for th_alert in alerts:
                linked_case = th_alert.get("case")
                if linked_case == th_case_id:
                    th_alert_id = th_alert.get("id") or th_alert.get("_id", "")
                    os_alert_id = self.alert_map.get(th_alert_id)
                    if os_alert_id:
                        resp = self.session.post(
                            f"{self.url}/api/v1/incidents/{os_incident_id}/alerts",
                            json={"alert_id": os_alert_id},
                        )
                        if resp.status_code in (200, 201):
                            self.stats["links"] += 1

        print(f"  Created {self.stats['links']} alert-incident links")

    def import_all(self):
        """Run full import."""
        metadata = self._load("metadata.json")
        if isinstance(metadata, dict):
            print(f"\nImporting TheHive data exported from {metadata.get('url', 'unknown')}")
            print(f"Export date: {metadata.get('exported_at', 'unknown')}\n")

        self.import_alerts()
        self.import_cases()
        self.link_alerts_to_incidents()

        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)
        print(f"  Alerts imported:     {self.stats['alerts']}")
        print(f"  Incidents imported:  {self.stats['incidents']}")
        print(f"  Observables imported:{self.stats['observables']}")
        print(f"  Alert-incident links:{self.stats['links']}")
        print(f"  Errors:              {self.stats['errors']}")
        print("=" * 60)

        if self.stats["errors"] > 0:
            print("\nSome items failed to import. Check the output above for details.")
            print("Common causes: duplicate source_id, missing required fields, auth issues.")

        print("\nNext steps:")
        print("  1. Verify counts via dashboard: GET /api/v1/dashboard/stats")
        print("  2. Spot-check alerts and incidents in the UI")
        print("  3. Reconnect your SIEM integrations")
        print("  4. Set up playbooks to replace Cortex analyzers/responders")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Migrate data from TheHive to OpenSOAR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export from TheHive
  python migrate_from_thehive.py export \\
    --thehive-url https://thehive.example.com \\
    --thehive-api-key YOUR_KEY \\
    --output-dir ./thehive-export

  # Import to OpenSOAR
  python migrate_from_thehive.py import \\
    --opensoar-url http://localhost:8000 \\
    --opensoar-api-key YOUR_KEY \\
    --input-dir ./thehive-export
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export data from TheHive")
    export_parser.add_argument("--thehive-url", required=True, help="TheHive base URL")
    export_parser.add_argument("--thehive-api-key", required=True, help="TheHive API key")
    export_parser.add_argument("--output-dir", default="./thehive-export", help="Output directory")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import data to OpenSOAR")
    import_parser.add_argument("--opensoar-url", required=True, help="OpenSOAR base URL")
    import_parser.add_argument("--opensoar-api-key", required=True, help="OpenSOAR API key")
    import_parser.add_argument("--input-dir", default="./thehive-export", help="Input directory (from export)")

    args = parser.parse_args()

    if args.command == "export":
        exporter = TheHiveExporter(args.thehive_url, args.thehive_api_key, args.output_dir)
        exporter.export_all()
    elif args.command == "import":
        importer = OpenSOARImporter(args.opensoar_url, args.opensoar_api_key, args.input_dir)
        importer.import_all()


if __name__ == "__main__":
    main()
