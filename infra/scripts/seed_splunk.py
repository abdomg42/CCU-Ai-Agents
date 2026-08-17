"""Seed Splunk with mock logs via the HTTP Event Collector (HEC).

Usage:
    # Automatic mode: enable HEC, create token, push logs (needs admin password)
    python infra/scripts/seed_splunk.py

    # Token-only mode: if you already created an HEC token in the Splunk UI
    python infra/scripts/seed_splunk.py --hec-token YOUR-HEC-TOKEN

Prerequisites:
    Splunk must be running with management port 8089 and HEC port 8088 exposed.
    Web UI: https://localhost:18000 (admin / SplunkAdmin123!)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

import urllib3
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SPLUNK_HOST = "localhost"
DEFAULT_MGMT_PORT = 8088
DEFAULT_HEC_PORT = 8089
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "SplunkAdmin123!"
DEFAULT_INDEX = "main"
DEFAULT_SOURCE = "ccu"
DEFAULT_SOURCETYPE = "_json"


def _request(
    method: str,
    url: str,
    auth: tuple[str, str] | None = None,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    expected: tuple[int, ...] = (200, 201),
) -> urllib3.HTTPResponse:
    http = urllib3.PoolManager(cert_reqs="CERT_NONE")
    encoded_body = urllib.parse.urlencode(body) if body else None
    response = http.request(
        method,
        url,
        body=encoded_body,
        headers=headers or {},
        auth=auth,
    )
    if response.status not in expected:
        raise RuntimeError(
            f"Splunk API error {response.status}: {response.data.decode('utf-8', errors='ignore')[:500]}"
        )
    return response


def _wait_for_splunk(host: str, port: int, auth: tuple[str, str], timeout: int = 180) -> None:
    url = f"https://{host}:{port}/services/server/info"
    logger.info("Waiting for Splunk management API at %s...", url)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = _request("GET", url, auth, expected=(200,))
            if b"<title>Server info" in resp.data or b"serverName" in resp.data:
                logger.info("Splunk management API is ready.")
                return
        except Exception as exc:
            logger.debug("Splunk not ready yet: %s", exc)
        time.sleep(5)
    raise TimeoutError(f"Splunk management API did not become ready within {timeout}s")


def _enable_hec(host: str, port: int, auth: tuple[str, str], hec_port: int) -> None:
    url = f"https://{host}:{port}/services/data/inputs/http/http"
    logger.info("Enabling HEC on port %s...", hec_port)
    _request(
        "POST",
        url,
        auth,
        body={"disabled": "false", "enableSSL": "false", "port": str(hec_port)},
    )
    logger.info("HEC enabled.")


def _extract_token_value(xml: str) -> str | None:
    match = re.search(r'name="token">([0-9a-f-]+)</\w+:?key>', xml, re.DOTALL)
    return match.group(1) if match else None


def _get_or_create_token(
    host: str,
    port: int,
    auth: tuple[str, str],
    token_name: str = "ccu_hec",
) -> str:
    list_url = f"https://{host}:{port}/services/data/inputs/http"
    logger.info("Checking existing HEC tokens...")
    resp = _request("GET", list_url, auth)
    data = resp.data.decode("utf-8", errors="ignore")
    if f'<title>{token_name}</title>' in data:
        token = _extract_token_value(data)
        if token:
            logger.info("Reusing existing HEC token.")
            return token

    create_url = f"https://{host}:{port}/services/data/inputs/http"
    logger.info("Creating HEC token '%s'...", token_name)
    resp = _request(
        "POST",
        create_url,
        auth,
        body={
            "name": token_name,
            "index": DEFAULT_INDEX,
            "source": DEFAULT_SOURCE,
            "sourcetype": DEFAULT_SOURCETYPE,
        },
    )
    data = resp.data.decode("utf-8", errors="ignore")
    token = _extract_token_value(data)
    if not token:
        raise RuntimeError("Could not extract HEC token from Splunk response.")
    logger.info("HEC token created.")
    return token


def _push_logs(
    host: str,
    hec_port: int,
    token: str,
    logs: list[dict[str, Any]],
    hec_https: bool = False,
) -> int:
    protocol = "https" if hec_https else "http"
    url = f"{protocol}://{host}:{hec_port}/services/collector/event"
    headers = {"Authorization": f"Splunk {token}", "Content-Type": "application/json"}
    http = urllib3.PoolManager(cert_reqs="CERT_NONE")
    count = 0
    logger.info("Pushing %s log events to Splunk HEC...", len(logs))
    for log in logs:
        event = {
            "time": log.get("timestamp", ""),
            "source": DEFAULT_SOURCE,
            "sourcetype": DEFAULT_SOURCETYPE,
            "index": DEFAULT_INDEX,
            "event": log,
        }
        body = json.dumps(event, ensure_ascii=False).encode("utf-8")
        resp = http.request("POST", url, body=body, headers=headers)
        if resp.status not in (200, 201):
            logger.warning(
                "Failed to push log %s: %s",
                log.get("log_id"),
                resp.data.decode("utf-8", errors="ignore")[:200],
            )
        else:
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Splunk with mock logs via HEC")
    parser.add_argument("--host", default=DEFAULT_SPLUNK_HOST, help="Splunk host")
    parser.add_argument("--mgmt-port", type=int, default=DEFAULT_MGMT_PORT, help="Management port (default 8089)")
    parser.add_argument("--hec-port", type=int, default=DEFAULT_HEC_PORT, help="HEC port (default 8088)")
    parser.add_argument("--user", default=DEFAULT_ADMIN_USER, help="Splunk admin user")
    parser.add_argument("--password", default=DEFAULT_ADMIN_PASS, help="Splunk admin password")
    parser.add_argument("--hec-token", help="Existing HEC token (skips management API setup)")
    parser.add_argument("--hec-https", action="store_true", help="Use HTTPS for HEC (default: HTTP on port 8088)")
    parser.add_argument("--logs", default="mocks/mock_logs.json", help="Path to logs JSON file")
    args = parser.parse_args()

    logs_path = Path(args.logs)
    if not logs_path.exists():
        raise FileNotFoundError(f"Logs file not found: {logs_path}")
    with open(logs_path, encoding="utf-8") as f:
        logs = json.load(f)

    if args.hec_token:
        token = args.hec_token
        logger.info("Using provided HEC token, skipping management API.")
    else:
        auth = (args.user, args.password)
        _wait_for_splunk(args.host, args.mgmt_port, auth)
        _enable_hec(args.host, args.mgmt_port, auth, args.hec_port)
        token = _get_or_create_token(args.host, args.mgmt_port, auth)

    count = _push_logs(args.host, args.hec_port, token, logs, hec_https=args.hec_https)
    logger.info("Successfully pushed %s/%s log events to Splunk.", count, len(logs))


if __name__ == "__main__":
    main()
