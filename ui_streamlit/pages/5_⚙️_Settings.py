"""Page de configuration : backend actif, statut ingestion, relance."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import subprocess
import sys
from pathlib import Path
from typing import Any

import streamlit as st

from config.settings import get_settings
from ui_streamlit.shared import get_neo4j_client, load_custom_css

st.set_page_config(
    page_title="Settings — CCU Diagnostic Agent",
    page_icon="⚙️",
    layout="wide",
)

load_custom_css()


def fetch_graph_status() -> dict[str, int]:
    """Retourne le nombre de nœuds par label dans Neo4j."""
    client = get_neo4j_client()
    if client is None:
        return {}
    with client:
        nodes = client.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt")
    return {n["label"]: n["cnt"] for n in nodes}


def run_ingestion_subprocess() -> subprocess.CompletedProcess[str]:
    """Lance run_ingestion.py en subprocess et capture la sortie."""
    root = Path(__file__).resolve().parents[2]
    cmd = [sys.executable, "-m", "data.ingestion.run_ingestion"]
    return subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=600,
    )


def main() -> None:
    """Point d'entrée de la page settings."""
    st.title("⚙️ Settings")
    st.caption("Configuration et statut de l'ingestion.")

    settings = get_settings()

    st.subheader("Backend de ticketing")
    st.metric("Backend actif", settings.TICKETING_BACKEND.upper())
    st.write(f"ZAMMAD_URL : `{settings.ZAMMAD_URL}`")

    st.subheader("Statut Neo4j")
    graph_status = fetch_graph_status()
    if graph_status:
        cols = st.columns(min(len(graph_status), 6))
        for col, (label, count) in zip(cols, sorted(graph_status.items())):
            with col:
                st.metric(label, count)
    else:
        st.warning("Neo4j non joignable.")

    st.subheader("Relancer l'ingestion")
    st.write(
        "Cliquez ci-dessous pour exécuter `python -m data.ingestion.run_ingestion`. "
        "L'opération est idempotente."
    )

    if st.button("🚀 Relancer l'ingestion", type="primary"):
        with st.spinner("Ingestion en cours..."):
            result = run_ingestion_subprocess()
        st.subheader("Logs stdout")
        st.code(result.stdout, language="text")
        if result.stderr:
            st.subheader("Logs stderr")
            st.code(result.stderr, language="text")
        if result.returncode == 0:
            st.success("Ingestion terminée avec succès.")
        else:
            st.error(f"Ingestion terminée avec le code {result.returncode}.")


main()
