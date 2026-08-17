"""Interface de chat pour le Diagnostic Technique CCU."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import streamlit as st

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Chat — CCU Diagnostic Agent",
    page_icon="💬",
    layout="wide",
)

# Chargement du CSS personnalisé.
css_path = Path(__file__).resolve().parents[1] / "assets" / "custom.css"
if css_path.exists():
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def _extract_report_id(report_path: str | None) -> str:
    """Extrait l'identifiant du rapport depuis son chemin."""
    if not report_path:
        return ""
    name = Path(report_path).name
    return name.split(".")[0]


def _stream_events(backend_url: str, text: str):
    """Générateur qui yield chaque événement SSE renvoyé par le backend."""
    url = urljoin(backend_url.rstrip("/") + "/", "diagnose/stream")
    payload = {"text": text}

    with requests.post(url, json=payload, stream=True, timeout=300) as response:
        response.raise_for_status()
        buffer = ""
        for chunk in response.iter_content(chunk_size=1024):
            if not chunk:
                continue
            buffer += chunk.decode("utf-8")
            while "\n\n" in buffer:
                raw_event, buffer = buffer.split("\n\n", 1)
                for line in raw_event.splitlines():
                    if line.startswith("data: "):
                        data = line[len("data: "):].strip()
                        if data:
                            try:
                                yield json.loads(data)
                            except json.JSONDecodeError:
                                continue
                        break


def _render_trace_timeline(traces: list[dict[str, Any]]) -> str:
    """Retourne un markdown représentant la timeline des agents."""
    lines = ["**Agent trace**"]
    for trace in traces:
        node = trace.get("node", "")
        summary = trace.get("summary", "")
        lines.append(f"- **{node}** — {summary}")
    return "\n".join(lines)


def _render_report_card(result: dict[str, Any], backend_url: str) -> None:
    """Affiche la carte de rapport final."""
    root = result.get("root_cause") or {}
    mapping = result.get("ticket_mapping") or {}
    report_id = _extract_report_id(result.get("report_path"))
    recipients = result.get("email_recipients") or []

    is_linked = mapping.get("status") == "linked_to_existing"
    badge_text = (
        f"Similar incident found (ticket #{mapping.get('ticket_id', 'N/A')})"
        if is_linked
        else f"New ticket created (#{mapping.get('ticket_id', 'N/A')})"
    )
    score = mapping.get("similarity_score")
    if score is not None and score > 0:
        badge_text += f" — score {float(score):.2f}"

    st.subheader("Diagnostic Report")
    st.info(badge_text)

    st.markdown(
        f"""
**Root cause:** {root.get('cause', 'undetermined')}  
**Confidence:** {root.get('confidence', 'N/A')}
        """.strip()
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        if report_id:
            report_url = f"{backend_url.rstrip('/')}/reports/{report_id}"
            st.link_button("Download PDF report", report_url)
    with col2:
        if result.get("email_sent") and recipients:
            st.success(f"Email sent to {', '.join(recipients)}")


def main() -> None:
    """Point d'entrée de la page de chat."""
    st.title("CCU Diagnostic Agent")
    st.caption(
        "Describe an incident in natural language. The agent will diagnose, report, "
        "and notify — no automatic action is executed."
    )

    with st.sidebar:
        st.header("Configuration")
        backend_url = st.text_input("Backend URL", value=DEFAULT_BACKEND_URL)
        st.divider()
        st.markdown("**Exemple de message :**")
        st.markdown(
            "Client acc-12345, service svc-fiber-12345, commande ord-2026-001. "
            "Coupure Internet fibre."
        )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["content"])
            else:
                st.markdown(message["trace_md"])
                if message.get("result"):
                    _render_report_card(message["result"], backend_url)

    if prompt := st.chat_input("Describe the incident in natural language..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            traces: list[dict[str, Any]] = []
            trace_placeholder = st.empty()
            report_placeholder = st.empty()

            try:
                for event in _stream_events(backend_url, prompt):
                    node = event.get("node")
                    if node == "final":
                        result = event.get("result") or {}
                        with report_placeholder:
                            _render_report_card(result, backend_url)
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "trace_md": _render_trace_timeline(traces),
                                "result": result,
                            }
                        )
                    else:
                        traces.append(event)
                        trace_placeholder.markdown(_render_trace_timeline(traces))
            except requests.RequestException as exc:
                error_msg = f"Erreur de connexion au backend : {exc}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "trace_md": f"**error** — {error_msg}",
                        "result": None,
                    }
                )


main()
