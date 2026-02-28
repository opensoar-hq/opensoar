"""Polls Elasticsearch for security events and forwards them to OpenSOAR.

This replaces the need for an Elastic webhook connector (which requires
a paid license). It watches an Elasticsearch index for new events and
sends them to OpenSOAR's webhook endpoint.

Usage:
    python scripts/elastic_poller.py

Environment variables:
    ELASTIC_URL     - Elasticsearch URL (default: http://localhost:9200)
    ELASTIC_USER    - Elasticsearch username (default: elastic)
    ELASTIC_PASS    - Elasticsearch password (default: elastic_dev)
    ELASTIC_INDEX   - Index pattern to watch (default: security-events-*)
    SOAR_URL        - OpenSOAR webhook URL (default: http://localhost:8000/api/v1/webhooks/alerts/elastic)
    POLL_INTERVAL   - Seconds between polls (default: 10)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError


ELASTIC_URL = os.getenv("ELASTIC_URL", "http://localhost:9200")
ELASTIC_USER = os.getenv("ELASTIC_USER", "elastic")
ELASTIC_PASS = os.getenv("ELASTIC_PASS", "elastic_dev")
ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "security-events-*")
SOAR_URL = os.getenv("SOAR_URL", "http://localhost:8000/api/v1/webhooks/alerts/elastic")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))


def elastic_request(path: str, body: dict | None = None) -> dict:
    import base64
    url = f"{ELASTIC_URL}/{path}"
    creds = base64.b64encode(f"{ELASTIC_USER}:{ELASTIC_PASS}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urlopen(req) as resp:
        return json.loads(resp.read().decode())


def send_to_soar(event: dict) -> dict:
    data = json.dumps(event).encode()
    req = Request(SOAR_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req) as resp:
        return json.loads(resp.read().decode())


def main():
    print(f"Elastic Poller starting...")
    print(f"  Elasticsearch: {ELASTIC_URL}/{ELASTIC_INDEX}")
    print(f"  OpenSOAR webhook:  {SOAR_URL}")
    print(f"  Poll interval: {POLL_INTERVAL}s")
    print()

    last_timestamp = datetime.now(timezone.utc).isoformat()

    while True:
        try:
            query = {
                "query": {
                    "range": {
                        "@timestamp": {"gt": last_timestamp}
                    }
                },
                "sort": [{"@timestamp": "asc"}],
                "size": 100,
            }

            result = elastic_request(f"{ELASTIC_INDEX}/_search", query)
            hits = result.get("hits", {}).get("hits", [])

            if hits:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(hits)} new event(s)")

                for hit in hits:
                    source = hit["_source"]
                    source["_id"] = hit["_id"]
                    source["_index"] = hit["_index"]

                    try:
                        resp = send_to_soar(source)
                        print(f"  -> {resp.get('title', 'Unknown')} "
                              f"(severity={resp.get('severity')}, "
                              f"playbooks={resp.get('playbooks_triggered', [])})")
                    except URLError as e:
                        print(f"  ERROR sending to OpenSOAR: {e}")

                    ts = source.get("@timestamp", last_timestamp)
                    if ts > last_timestamp:
                        last_timestamp = ts

        except URLError as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Elasticsearch poll error: {e}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
