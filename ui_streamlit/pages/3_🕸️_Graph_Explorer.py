"""Exploration interactive du sous-graphe d'un incident."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from typing import Any

import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph

from ui_streamlit.shared import get_neo4j_client, load_custom_css

st.set_page_config(
    page_title="Graph Explorer — CCU Diagnostic Agent",
    page_icon="🕸️",
    layout="wide",
)

load_custom_css()


_LABEL_COLORS = {
    "Client": "#4c8bf5",
    "Order": "#f5b94c",
    "Product": "#34a853",
    "Incident": "#ea4335",
    "Ticket": "#9aa0a6",
    "LogEvent": "#d7aefb",
}


def fetch_subgraph(incident_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retourne les nœuds et relations du sous-graphe autour d'un incident."""
    client = get_neo4j_client()
    if client is None:
        return [], []

    with client:
        result = client.run(
            """
            MATCH path = (start:Incident|Ticket {id: $id})-[:HAS_INCIDENT|FOR_PRODUCT|DOCUMENTED_BY|LOGGED|HAS_ORDER|BELONGS_TO_ORDER|PLACED_ORDER|HAS_SUBSCRIPTION|SUBSCRIBED_TO|FOR_SERVICE|BELONGS_TO_SERVICE*1..2]-(n)
            RETURN DISTINCT
              [x IN nodes(path) | {id: x.id, labels: labels(x), props: properties(x)}] AS nodes,
              [r IN relationships(path) | {start: startNode(r).id, end: endNode(r).id, type: type(r)}] AS rels
            LIMIT 100
            """,
            {"id": incident_id},
        )

    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for row in result:
        for node in row.get("nodes", []):
            labels = node.get("labels", [])
            label = labels[0] if labels else "Unknown"
            props = node.get("props") or {}
            node_id = node.get("id") or props.get("id") or str(id(node))
            nodes_by_id[node_id] = {
                "id": node_id,
                "label": label,
                "name": props.get("name") or props.get("short_description") or label,
            }
        for rel in row.get("rels", []):
            start_id = rel.get("start")
            end_id = rel.get("end")
            rel_type = rel.get("type", "REL")
            if start_id and end_id:
                key = (start_id, end_id, rel_type)
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append(key)

    return list(nodes_by_id.values()), edges


def build_agraph(nodes: list[dict[str, Any]], edges: list[tuple[str, str, str]]) -> list[Node] | list[Edge]:
    """Construit les objets Node/Edge pour streamlit-agraph."""
    agraph_nodes = [
        Node(
            id=n["id"],
            label=f"{n['label']}\n{n['name'][:30]}",
            title=n["name"],
            color=_LABEL_COLORS.get(n["label"], "#9aa0a6"),
            size=25,
        )
        for n in nodes
    ]
    agraph_edges = [
        Edge(source=s, target=t, label=rel, arrows="to", color="#5f6368")
        for s, t, rel in edges
    ]
    return agraph_nodes, agraph_edges


def main() -> None:
    """Point d'entrée du graph explorer."""
    st.title("🕸️ Graph Explorer")
    st.caption("Visualisez le sous-graphe Client-Order-Product-Incident-LogEvent-Ticket.")

    incident_id = st.text_input(
        "Incident / Ticket ID",
        placeholder="INC0000045 ou TICK-CCU-XXXX",
    )

    if not incident_id:
        st.info("Saisissez un incident_id ou ticket_id pour afficher son sous-graphe.")
        return

    with st.spinner("Recherche du sous-graphe..."):
        nodes, edges = fetch_subgraph(incident_id)

    if not nodes:
        st.warning(f"Aucun nœud trouvé pour `{incident_id}`.")
        return

    agraph_nodes, agraph_edges = build_agraph(nodes, edges)

    config = Config(
        height=600,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlighting=True,
        highlightColor="#F7A7A6",
        collapsible=False,
    )

    st.write(f"**{len(nodes)} nœuds** — **{len(edges)} relations**")
    agraph(nodes=agraph_nodes, edges=agraph_edges, config=config)


main()
