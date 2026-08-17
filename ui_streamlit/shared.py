"""Utilitaires partagés entre les pages Streamlit."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)


def load_custom_css() -> None:
    """Injecte le CSS personnalisé si présent."""
    css_path = Path(__file__).resolve().parent / "assets" / "custom.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def get_neo4j_client() -> Any:
    """Retourne une instance Neo4jClient ou None si indisponible."""
    try:
        from graph.graph_client import Neo4jClient

        client = Neo4jClient()
        client.verify_connectivity()
        return client
    except Exception as exc:
        logger.warning("Neo4j indisponible : %s", exc)
        st.warning("Neo4j n'est pas joignable. Certaines données sont indisponibles.")
        return None


def get_postgres_client() -> Any:
    """Retourne un client Postgres ou None si indisponible."""
    try:
        import psycopg2

        from config.settings import get_settings

        settings = get_settings()
        return psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )
    except Exception as exc:
        logger.warning("Postgres indisponible : %s", exc)
        return None
