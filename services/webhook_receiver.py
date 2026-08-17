"""Receiver HTTP qui publie les événements entrants dans Kafka.

Le broker cible est `kafka:9092` sous Docker et `localhost:9092` en local.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import FastAPI, Request
from kafka import KafkaProducer

logger = logging.getLogger(__name__)

app = FastAPI(title="CCU Webhook Receiver")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "ccu-incidents")


@app.on_event("startup")
def _startup() -> None:
    app.state.producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False, default=str).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
    )
    logger.info("Webhook receiver connecté à Kafka : %s", KAFKA_BOOTSTRAP_SERVERS)


@app.on_event("shutdown")
def _shutdown() -> None:
    if hasattr(app.state, "producer"):
        app.state.producer.close()


@app.post("/webhook/{source}")
async def receive_webhook(source: str, request: Request) -> dict[str, Any]:
    """Reçoit un webhook externe et le publie sur Kafka."""
    payload = await request.json()
    event = {
        "source": source,
        "payload": payload,
        "headers": dict(request.headers),
    }
    app.state.producer.send(
        KAFKA_TOPIC,
        key=source,
        value=event,
    )
    logger.info("Webhook %s publié sur %s", source, KAFKA_TOPIC)
    return {"status": "published", "topic": KAFKA_TOPIC, "source": source}
