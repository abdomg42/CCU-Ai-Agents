"""Dashboard : KPIs et visualisations Plotly."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_DIR = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

from collections import defaultdict
from datetime import datetime
from typing import Any

import plotly.express as px
import streamlit as st

try:
    from ui_streamlit.shared import get_neo4j_client, load_custom_css
except ModuleNotFoundError:
    from shared import get_neo4j_client, load_custom_css

st.set_page_config(
    page_title="Dashboard — CCU Diagnostic Agent",
    page_icon="📊",
    layout="wide",
)

load_custom_css()


def _parse_date(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def fetch_dashboard_data() -> dict[str, Any]:
    """Interroge Neo4j pour les indicateurs du dashboard."""
    client = get_neo4j_client()
    data = {
        "incidents_over_time": [],
        "by_category": [],
        "by_product": [],
        "confidence_distribution": {"Faible": 0, "Moyen": 0, "Élevé": 0},
        "mapping_stats": {"linked": 0, "created": 0, "unknown": 0},
        "avg_pipeline_seconds": None,
        "node_counts": {},
    }
    if client is None:
        return data

    with client:
        # Incidents dans le temps.
        incidents = client.run(
            """
            MATCH (i:Incident)
            RETURN i.opened_at AS opened_at, i.closed_at AS closed_at, i.status AS status
            """
        )
        counts: dict[str, int] = defaultdict(int)
        for row in incidents:
            day = _parse_date(row.get("opened_at") or row.get("closed_at"))
            if day:
                counts[day] += 1
        data["incidents_over_time"] = [
            {"date": d, "count": c} for d, c in sorted(counts.items())
        ]

        # Par catégorie.
        cats = client.run(
            "MATCH (i:Incident) RETURN i.category AS category, count(i) AS cnt"
        )
        data["by_category"] = [
            {"category": c["category"] or "Non classé", "count": c["cnt"]}
            for c in cats
        ]

        # Par produit.
        prods = client.run(
            """
            MATCH (i:Incident)-[:FOR_PRODUCT]->(p:Product)
            RETURN p.name AS product, count(i) AS cnt
            """
        )
        data["by_product"] = [
            {"product": p["product"] or "Non lié", "count": p["cnt"]}
            for p in prods
        ]

        # Distribution de confiance (root_cause reasoner) sur les N derniers incidents.
        recent = client.run(
            """
            MATCH (i:Incident)
            WHERE i.root_cause IS NOT NULL
            RETURN i.root_cause AS root_cause
            ORDER BY i.opened_at DESC
            LIMIT 500
            """
        )
        for row in recent:
            rc = str(row.get("root_cause", "")).lower()
            if "high" in rc or "élevé" in rc or "elevated" in rc:
                data["confidence_distribution"]["Élevé"] += 1
            elif "medium" in rc or "moyen" in rc or "moderate" in rc:
                data["confidence_distribution"]["Moyen"] += 1
            elif "low" in rc or "faible" in rc:
                data["confidence_distribution"]["Faible"] += 1
            else:
                data["confidence_distribution"]["Moyen"] += 1

        # Mapping : liés vs créés.
        linked = client.run(
            "MATCH (t:Ticket)-[:DOCUMENTED_BY]->(:Order) RETURN count(t) AS cnt"
        )
        created = client.run(
            "MATCH (t:Ticket) WHERE NOT (t)-[:DOCUMENTED_BY]->(:Order) RETURN count(t) AS cnt"
        )
        data["mapping_stats"] = {
            "linked": linked[0]["cnt"] if linked else 0,
            "created": created[0]["cnt"] if created else 0,
        }

        # Temps de traitement moyen depuis audit.log si disponible.
        from config.settings import get_settings

        audit_path = get_settings().AUDIT_LOG_PATH
        durations = []
        if audit_path.exists():
            import json

            for line in audit_path.read_text().splitlines():
                try:
                    entry = json.loads(line)
                    if entry.get("event_type") == "pipeline_end":
                        payload = entry.get("payload", {})
                        elapsed = payload.get("elapsed_seconds")
                        if elapsed is not None:
                            durations.append(float(elapsed))
                except (json.JSONDecodeError, ValueError):
                    continue
        if durations:
            data["avg_pipeline_seconds"] = sum(durations) / len(durations)

        # Nœuds par label.
        nodes = client.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt")
        data["node_counts"] = {n["label"]: n["cnt"] for n in nodes}

    return data


def main() -> None:
    """Point d'entrée du dashboard."""
    st.title("📊 Dashboard")
    st.caption("Métriques et tendances du pipeline de diagnostic.")

    data = fetch_dashboard_data()

    # Cartes en haut.
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Incidents", data["node_counts"].get("Incident", 0))
    with col2:
        st.metric("Tickets", data["node_counts"].get("Ticket", 0))
    with col3:
        st.metric("Clients", data["node_counts"].get("Client", 0))
    with col4:
        st.metric("Logs", data["node_counts"].get("LogEvent", 0))

    st.divider()

    # Graphiques.
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Incidents traités dans le temps")
        if data["incidents_over_time"]:
            df_time = px.line(
                data["incidents_over_time"],
                x="date",
                y="count",
                markers=True,
            )
            df_time.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(df_time, width=True)
        else:
            st.info("Aucune donnée temporelle disponible.")

    with col_right:
        st.subheader("Répartition par catégorie")
        if data["by_category"]:
            df_cat = px.bar(
                data["by_category"],
                x="category",
                y="count",
                color="category",
            )
            df_cat.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            st.plotly_chart(df_cat, width=True)
        else:
            st.info("Aucune catégorie disponible.")

    col_left2, col_right2 = st.columns(2)

    with col_left2:
        st.subheader("Répartition par produit")
        if data["by_product"]:
            df_prod = px.bar(
                data["by_product"],
                x="product",
                y="count",
                color="product",
            )
            df_prod.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            st.plotly_chart(df_prod, width=True)
        else:
            st.info("Aucun produit lié.")

    with col_right2:
        st.subheader("Distribution du niveau de confiance")
        conf_df = [
            {"Niveau": k, "Incidents": v}
            for k, v in data["confidence_distribution"].items()
            if v
        ]
        if conf_df:
            df_conf = px.pie(conf_df, names="Niveau", values="Incidents")
            df_conf.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(df_conf, width=True)
        else:
            st.info("Aucune donnée de confiance.")

    col_left3, col_right3 = st.columns(2)

    with col_left3:
        st.subheader("Taux de mapping")
        mapping_total = sum(data["mapping_stats"].values()) or 1
        mapping_df = [
            {"Statut": "Lié à un ticket", "Count": data["mapping_stats"]["linked"]},
            {"Statut": "Nouveau ticket", "Count": data["mapping_stats"]["created"]},
        ]
        df_map = px.bar(mapping_df, x="Statut", y="Count", color="Statut")
        df_map.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        st.plotly_chart(df_map, width=True)
        st.caption(
            f"Liés : {data['mapping_stats']['linked']} / "
            f"Créés : {data['mapping_stats']['created']}"
        )

    # with col_right3:
    #     st.subheader("Temps de traitement moyen")
    #     avg = data["avg_pipeline_seconds"]
    #     if avg is not None:
    #         st.metric("Durée moyenne", f"{avg:.2f} s")
    #     else:
    #         st.info("Aucun audit pipeline disponible.")


main()
