"""SOMA 智者思维面板 — Streamlit Dashboard"""
import sys
from pathlib import Path

# 确保 soma 在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from soma.config import SOMAConfig, load_config
from soma.agent import SOMA_Agent

from dash.components.chat_tab import render_chat_tab
from dash.components.memory_tab import render_memory_tab
from dash.components.framework_tab import render_framework_tab


st.set_page_config(
    page_title="SOMA — 智者思维面板",
    page_icon="🧠",
    layout="wide",
)


@st.cache_resource
def init_agent():
    config_path = Path.cwd() / "wisdom_laws.yaml"
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / "wisdom_laws.yaml"
    framework = load_config(config_path)
    config = SOMAConfig(
        framework=framework,
        episodic_persist_dir=Path("dashboard_data"),
        default_top_k=5,
        recall_threshold=0.01,
        use_vector_search=False,
    )
    return SOMA_Agent(config)


def main():
    st.title("🧠 SOMA — 体悟式智慧架构")

    agent = init_agent()

    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📚 Memory", "⚖️ Framework"])

    with tab1:
        render_chat_tab(agent)

    with tab2:
        render_memory_tab(agent)

    with tab3:
        render_framework_tab(agent)


if __name__ == "__main__":
    main()
