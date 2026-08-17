"""Client bas-niveau pour peupler la base CRM Postgres (clients / abonnements)."""
from __future__ import annotations

import logging
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)


class PostgresCRMClient:
    """Connexion et écriture idempotente des clients dans Postgres."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> None:
        settings = get_settings()
        self.host = host or settings.POSTGRES_HOST
        self.port = port or settings.POSTGRES_PORT
        self.user = user or settings.POSTGRES_USER
        self.password = password or settings.POSTGRES_PASSWORD
        self.database = database or settings.POSTGRES_DB
        self._conn = None

    def connect(self) -> None:
        import psycopg2

        self._conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
        )
        self._conn.autocommit = False

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "PostgresCRMClient":
        self.connect()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _ensure_schema(self) -> None:
        """Crée la table clients si elle n'existe pas."""
        from psycopg2.extras import execute_values

        _ = execute_values  # import explicite pour éviter l'avertissement
        with self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id VARCHAR PRIMARY KEY,
                    tenure INTEGER,
                    contract VARCHAR,
                    monthly_charges NUMERIC,
                    total_charges NUMERIC,
                    churn VARCHAR,
                    ingested_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
        self._conn.commit()

    def upsert_clients(self, clients: list[dict[str, Any]]) -> int:
        """Insère ou met à jour les clients et retourne le nombre traité."""
        self._ensure_schema()
        if not clients:
            return 0

        rows = [
            (
                c.get("id"),
                int(c["tenure"]) if c.get("tenure") is not None else None,
                c.get("contract"),
                float(c["monthly_charges"]) if c.get("monthly_charges") is not None else None,
                float(c["total_charges"]) if c.get("total_charges") is not None else None,
                c.get("churn"),
            )
            for c in clients
            if c.get("id")
        ]

        with self._conn.cursor() as cur:
            from psycopg2.extras import execute_values

            execute_values(
                cur,
                """
                INSERT INTO clients (id, tenure, contract, monthly_charges, total_charges, churn)
                VALUES %s
                ON CONFLICT (id) DO UPDATE SET
                    tenure = EXCLUDED.tenure,
                    contract = EXCLUDED.contract,
                    monthly_charges = EXCLUDED.monthly_charges,
                    total_charges = EXCLUDED.total_charges,
                    churn = EXCLUDED.churn,
                    ingested_at = NOW()
                """,
                rows,
                page_size=1000,
            )
        self._conn.commit()
        logger.info("CRM Postgres : %s clients upsertés", len(rows))
        return len(rows)


def ingest_clients_to_postgres(clients: list[dict[str, Any]]) -> int:
    """Helper : upsert les clients dans Postgres et retourne le compte."""
    try:
        with PostgresCRMClient() as client:
            return client.upsert_clients(clients)
    except Exception as exc:
        logger.error("Impossible d'écrire dans Postgres : %s", exc)
        return 0
