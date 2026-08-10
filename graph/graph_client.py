"""Wrapper autour du driver officiel Neo4j (bolt) avec retry minimal."""
from __future__ import annotations

import logging
import time
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, TransientError

from config.settings import get_settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Client Neo4j bas-niveau : connexion, exécution de requêtes Cypher et retry."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        max_retries: int = 5,
        backoff_seconds: float = 1.0,
    ) -> None:
        settings = get_settings()
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.database = database or settings.NEO4J_DATABASE
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _with_retry(self, fn: Any, query: str, parameters: dict[str, Any] | None = None) -> Any:
        parameters = parameters or {}
        last_exception: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return fn(query, parameters)
            except (ServiceUnavailable, TransientError) as exc:
                last_exception = exc
                logger.warning("Neo4j retry %s/%s after error: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * attempt)
        raise last_exception or RuntimeError("Neo4j operation failed after retries")

    def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Exécute une requête en lecture et retourne une liste de records."""

        def _run(q: str, params: dict[str, Any]) -> list[dict[str, Any]]:
            with self._driver.session(database=self.database) as session:
                result = session.run(q, params)
                return [record.data() for record in result]

        return self._with_retry(_run, query, parameters)

    def write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Exécute une requête en écriture (MERGE/CREATE) et retourne les records."""

        def _write(q: str, params: dict[str, Any]) -> list[dict[str, Any]]:
            with self._driver.session(database=self.database) as session:

                def work(tx: Any) -> list[dict[str, Any]]:
                    result = tx.run(q, params)
                    return [record.data() for record in result]

                return session.execute_write(work)

        return self._with_retry(_write, query, parameters)

    def verify_connectivity(self) -> None:
        """Lève une exception si la connexion Neo4j n'est pas disponible."""
        self._driver.verify_connectivity()
