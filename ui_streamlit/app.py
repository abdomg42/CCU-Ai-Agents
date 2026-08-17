"""Page d'accueil : redirige automatiquement vers l'interface Chat."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

st.set_page_config(
    page_title="CCU Diagnostic Agent",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Chargement du CSS personnalisé.
css_path = Path(__file__).resolve().parent / "assets" / "custom.css"
if css_path.exists():
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown('<h1 class="hero-title">CCU Diagnostic Agent</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-subtitle">Interface unifiée de diagnostic, exploration du graphe et supervision des tickets.</p>',
    unsafe_allow_html=True,
)

st.info("Sélectionnez une page dans le menu de gauche pour commencer.")

# Affiche un aperçu des pages disponibles.
col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("pages/1_💬_Chat.py", label="💬 Chat", icon="💬")
with col2:
    st.page_link("pages/2_📊_Dashboard.py", label="📊 Dashboard", icon="📊")
with col3:
    st.page_link("pages/3_🕸️_Graph_Explorer.py", label="🕸️ Graph Explorer", icon="🕸️")

col4, col5 = st.columns(2)
with col4:
    st.page_link("pages/4_🎫_Tickets.py", label="🎫 Tickets", icon="🎫")
with col5:
    st.page_link("pages/5_⚙️_Settings.py", label="⚙️ Settings", icon="⚙️")
