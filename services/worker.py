"""Worker Kafka consommant les incidents et les envoyant au pipeline.

Le broker cible est `kafka:9092` sous Docker et `localhost:9092` en local.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from kafka import KafkaConsumer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "ccu-incidents")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "ccu-worker")


def _process_event(event: dict[str, Any]) -> dict[str, Any]:
    """Intègre l'événement dans le pipeline de diagnostic."""
    logger.info("Traitement de l'événement %s", event.get("source"))
    # Ici on peut appeler l'API FastAPI ou directement l'orchestrateur LangGraph.
    return {"status": "processed", "event_source": event.get("source")}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        group_id=KAFKA_GROUP_ID,
        auto_offset_reset="earliest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    logger.info("Worker démarré : topic=%s, brokers=%s", KAFKA_TOPIC, KAFKA_BOOTSTRAP_SERVERS)

    try:
        for message in consumer:
            try:
                _process_event(message.value)
            except Exception as exc:
                logger.exception("Erreur de traitement du message : %s", exc)
    except KeyboardInterrupt:
        logger.info("Arrêt du worker.")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
