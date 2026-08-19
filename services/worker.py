"""Worker Kafka consommant les incidents et les envoyant au pipeline de diagnostic.

Le broker cible est `kafka:9092` sous Docker et `localhost:9092` en local.
Lorsqu'un événement est reçu, il est transmis à l'API /diagnose qui exécute le
pipeline LangGraph complet (PDF, email, note Zammad).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import httpx
from kafka import KafkaConsumer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "ccu-incidents")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "ccu-worker")
DIAGNOSE_API_URL = os.getenv("DIAGNOSE_API_URL", "http://localhost:8000/diagnose")


def _strip_html(text: Any) -> str:
    """Supprime les balises HTML renvoyées par certains webhooks (Zammad, Splunk)."""
    if not isinstance(text, str):
        return ""
    # Supprime les balises, puis décode les entités HTML courantes.
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return text.strip()


def _zammad_priority(priority: Any) -> str:
    """Convertit la priorité Zammad en code P1-P4."""
    if isinstance(priority, dict):
        priority = priority.get("name") or ""
    if not isinstance(priority, str):
        return "P3"
    lowered = priority.lower()
    if "high" in lowered or "3" in lowered:
        return "P1"
    if "normal" in lowered or "2" in lowered:
        return "P2"
    if "low" in lowered or "1" in lowered:
        return "P3"
    return "P3"


def _is_diagnostic_loop(description: str) -> bool:
    """Évite les boucles : un note Zammad générée par le système ne doit pas être re-traitée."""
    lowered = description.lower()
    return "rapport de diagnostic généré" in lowered or "ccu diagnostic agent" in lowered


def _extract_incident(event: dict[str, Any]) -> dict[str, Any] | None:
    """Extrait les champs title/description d'un événement Kafka."""
    payload = event.get("payload") or event.get("event") or event
    if not isinstance(payload, dict):
        return None

    title = _strip_html(
        payload.get("title") or payload.get("subject") or payload.get("summary") or "Incident"
    )

    # Zammad webhooks nest the first article under `article.body`.
    article = payload.get("article") or {}
    description = _strip_html(
        payload.get("description")
        or article.get("body")
        or payload.get("body")
        or payload.get("message")
        or payload.get("text")
        or ""
    )
    # Some ticketing systems (e.g. Zammad) create tickets with empty body.
    if not description:
        description = title

    # Évite les boucles causées par des déclencheurs Zammad sur "ticket updated".
    if _is_diagnostic_loop(description):
        logger.info("Événement ignoré : note de diagnostic détectée")
        return None

    return {
        "title": title,
        "description": description,
        "source": event.get("source", "kafka"),
        "priority": _zammad_priority(payload.get("priority", "P3")),
        "metadata": {k: v for k, v in payload.items() if k not in {"title", "description", "body", "text"}},
    }


MAX_RETRIES = 3
RETRY_DELAY = 3.0


def _process_event(event: dict[str, Any]) -> dict[str, Any]:
    """Appelle l'API /diagnose avec l'incident extrait (avec retry sur erreurs 5xx)."""
    incident = _extract_incident(event)
    if not incident:
        logger.warning("Événement ignoré, impossible d'extraire un incident : %s", event)
        return {"status": "skipped", "reason": "no_incident"}

    logger.info("Envoi de l'incident à %s : %s", DIAGNOSE_API_URL, incident.get("title"))

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=300.0) as client:
                response = client.post(DIAGNOSE_API_URL, json=incident)
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if 500 <= status < 600 and attempt < MAX_RETRIES:
                logger.warning(
                    "API diagnose %s (tentative %s/%s), nouvel essai dans %ss",
                    status,
                    attempt,
                    MAX_RETRIES,
                    RETRY_DELAY,
                )
                time.sleep(RETRY_DELAY)
                continue
            logger.error("Échec appel API diagnose : %s %s", status, exc)
            return {"status": "failed", "reason": f"{status}: {exc}"}
        except Exception as exc:
            logger.exception("Échec appel API diagnose : %s", exc)
            return {"status": "failed", "reason": str(exc)}
        else:
            logger.info(
                "Diagnostic terminé : report=%s, email_sent=%s, zammad_note=%s",
                result.get("report_path"),
                result.get("email_sent"),
                result.get("zammad_note_added"),
            )
            return {"status": "processed", "incident": incident.get("title"), "result": result}

    return {"status": "failed", "reason": str(last_error)}


def _create_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        group_id=KAFKA_GROUP_ID,
        auto_offset_reset="earliest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        session_timeout_ms=30000,
        heartbeat_interval_ms=10000,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("Worker connecté à Kafka : %s, topic=%s", KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC)
    logger.info("API diagnose cible : %s", DIAGNOSE_API_URL)

    consumer = _create_consumer()
    logger.info("Worker démarré, en attente de messages...")

    try:
        while True:
            try:
                for message in consumer:
                    try:
                        _process_event(message.value)
                    except Exception as exc:
                        logger.exception("Erreur de traitement du message : %s", exc)
            except ValueError as exc:
                # kafka-python on Windows sometimes raises socket/selector errors.
                logger.warning("Kafka transient error (Windows socket), recreating consumer: %s", exc)
                try:
                    consumer.close()
                except Exception:
                    pass
                import time
                time.sleep(2)
                consumer = _create_consumer()
            except KeyboardInterrupt:
                raise
    except KeyboardInterrupt:
        logger.info("Arrêt du worker.")
    finally:
        try:
            consumer.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
