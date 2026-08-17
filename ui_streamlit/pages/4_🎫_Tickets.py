"""Liste des tickets via le backend de ticketing actif."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_DIR = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

from typing import Any

import pandas as pd
import streamlit as st

from tools.ticketing import get_ticketing_backend

try:
    from ui_streamlit.shared import load_custom_css
except ModuleNotFoundError:
    from shared import load_custom_css

st.set_page_config(
    page_title="Tickets — CCU Diagnostic Agent",
    page_icon="🎫",
    layout="wide",
)

load_custom_css()


def fetch_tickets(status_filter: str, category_filter: str, priority_filter: str) -> list[dict[str, Any]]:
    """Interroge le backend configuré et filtre les résultats."""
    try:
        backend = get_ticketing_backend()
        # Zammad search ne supportant pas de filtres structurés, on fait une recherche large.
        raw = backend.search_tickets("*", limit=500)
    except Exception as exc:
        st.error(f"Impossible de contacter le backend ticketing : {exc}")
        return []

    tickets = []
    for item in raw:
        tickets.append(
            {
                "id": item.get("id"),
                "title": item.get("title") or item.get("subject"),
                "state": item.get("state"),
                "priority": item.get("priority"),
                "group": item.get("group"),
                "customer": item.get("customer"),
                "updated_at": item.get("updated_at"),
                "mapping_status": _infer_mapping_status(item),
                "category": _extract_category(item),
            }
        )

    if status_filter != "Tous":
        tickets = [t for t in tickets if t["mapping_status"] == status_filter]
    if category_filter != "Toutes":
        tickets = [t for t in tickets if t["category"] == category_filter]
    if priority_filter != "Toutes":
        tickets = [t for t in tickets if str(t["priority"]) == priority_filter]

    return tickets


def _infer_mapping_status(item: dict[str, Any]) -> str:
    title = str(item.get("title", "")).lower()
    if "similar" in title or "linked" in title:
        return "Lié à existant"
    return "Nouveau"


def _extract_category(item: dict[str, Any]) -> str:
    tags = item.get("tags", [])
    if tags:
        return str(tags[0])
    title = str(item.get("title", "")).lower()
    for cat in ["fiber", "mobile", "billing", "lan", "ccu"]:
        if cat in title:
            return cat
    return "ccu"


def main() -> None:
    """Point d'entrée de la page tickets."""
    st.title("🎫 Tickets")
    st.caption("Liste des tickets du backend de ticketing actif.")

    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Statut mapping", ["Tous", "Lié à existant", "Nouveau"])
    with col2:
        category_filter = st.selectbox("Catégorie", ["Toutes", "ccu", "fiber", "mobile", "billing", "lan"])
    with col3:
        priority_filter = st.selectbox("Priorité", ["Toutes", "1 critical", "2 high", "3 normal", "4 low"])

    with st.spinner("Chargement des tickets..."):
        tickets = fetch_tickets(status_filter, category_filter, priority_filter)

    if not tickets:
        st.info("Aucun ticket trouvé avec les filtres sélectionnés.")
        return

    df = pd.DataFrame(tickets)
    st.dataframe(df, width=True)
    st.caption(f"{len(tickets)} ticket(s) affiché(s).")


main()
