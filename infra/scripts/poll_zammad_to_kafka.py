"""Poll Zammad for recent tickets and push them to Kafka.

Usage:
    python infra/scripts/poll_zammad_to_kafka.py
    python infra/scripts/poll_zammad_to_kafka.py --since-minutes 10

The script fetches tickets from Zammad and publishes each one to the Kafka
topic `ccu-incidents`. The worker then consumes them and calls the
`/diagnose` API to run the full pipeline.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
from kafka import KafkaProducer

from config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "ccu-incidents")


def _zammad_client(base_url: str, token: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={
            "Authorization": f"Token token={token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _fetch_tickets(client: httpx.Client, since_minutes: int | None = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": 100, "expand": "true"}
    if since_minutes:
        # Zammad search syntax for created_at >= some time
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        date_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
        params["query"] = f"created_at:>={date_str}"

    logger.info("Fetching Zammad tickets with params: %s", params)
    response = client.get("/api/v1/tickets", params=params)
    response.raise_for_status()
    tickets = response.json()
    return tickets if isinstance(tickets, list) else []


def _fetch_article(client: httpx.Client, ticket_id: int | str) -> str:
    try:
        response = client.get(f"/api/v1/tickets/{ticket_id}?articles=true")
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", [])
        if articles:
            return str(articles[0].get("body", ""))
    except Exception as exc:
        logger.warning("Could not fetch article for ticket %s: %s", ticket_id, exc)
    return ""


def _ticket_to_event(ticket: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    ticket_id = ticket.get("id")
    title = ticket.get("title", "")
    body = _fetch_article(client, ticket_id) if ticket_id else ""
    if not body:
        body = ticket.get("article") or ticket.get("description") or ""
    # Some Zammad tickets have no article body; use the title as description.
    if not body:
        body = title

    return {
        "source": "zammad",
        "event": {
            "ticket_id": ticket.get("number") or str(ticket_id),
            "title": title,
            "description": body,
            "priority": ticket.get("priority", "P3"),
            "state": ticket.get("state", "new"),
            "customer": ticket.get("customer", ""),
            "group": ticket.get("group", ""),
        },
    }


def _push_to_kafka(events: list[dict[str, Any]]) -> int:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False, default=str).encode("utf-8"),
    )
    count = 0
    try:
        for event in events:
            future = producer.send(KAFKA_TOPIC, event)
            future.get(timeout=10)
            count += 1
            logger.info("Pushed ticket %s to Kafka topic %s", event["event"]["ticket_id"], KAFKA_TOPIC)
    finally:
        producer.close()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll Zammad tickets and push to Kafka")
    parser.add_argument("--since-minutes", type=int, default=None, help="Only fetch tickets created in the last N minutes")
    args = parser.parse_args()

    settings = get_settings()
    base_url = settings.ZAMMAD_URL
    token = settings.ZAMMAD_TOKEN
    if not base_url or not token:
        raise RuntimeError("ZAMMAD_URL and ZAMMAD_TOKEN must be configured in .env")

    with _zammad_client(base_url, token) as client:
        tickets = _fetch_tickets(client, args.since_minutes)
        logger.info("Found %s Zammad ticket(s)", len(tickets))

        events = [_ticket_to_event(ticket, client) for ticket in tickets]
        count = _push_to_kafka(events)

    logger.info("Successfully pushed %s/%s ticket(s) to Kafka.", count, len(tickets))


if __name__ == "__main__":
    main()
