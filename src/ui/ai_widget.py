"""
ai_widget.py
Universal Superset-Style Floating AI Analytics Copilot for the MSU SEO Intelligence Console.
Faithfully replicates the Superset Admissions Copilot floating widget:
- Floating circular sparkle trigger button (bottom-right: ✨ with green online dot).
- Floating elevated chat card with full dual Dark & White theme support.
- Monospace quantitative data tables, strategic deep dive accordion, and action pills.
- Solid teal 'Send' button (#20a7c9) and clean adaptive input field.
- Decoupled from scrolling: stays permanently fixed on screen across all views.
- Full multi-turn conversational memory.
"""
from __future__ import annotations

import os
from typing import Optional
import pandas as pd
import streamlit as st

from src.ai.agent import ask_ai_analyst
from src.ai.sql_executor import get_database_status
from src.ai.client import PROVIDERS_CONFIG

STARTER_TAGS = [
    ("📊 Top Blogs", "Top 10 blog posts by views"),
    ("🎓 Top Courses", "Top 5 courses by views and active users"),
    ("📱 Mobile vs Desktop", "Mobile vs Desktop traffic and conversion split"),
    ("🔎 Low CTR Queries", "High-impression search queries with low CTR (<2%)"),
    ("🎯 Total Leads", "Total Lead Form Conversions (Key Events)"),
    ("📈 Daily Trends", "Daily traffic trends over time"),
]


def render_ai_widget():
    """
    Renders the universal Superset-style Floating AI Copilot on every view:
    1. A floating circular sparkle trigger button in the bottom-right corner.
    2. A floating elevated card (when open) with live quantitative data tables,
       BLUF executive narrative, strategic deep dive accordions, and quick tags.
    3. Multi-turn conversational memory active across all queries.
    4. Adaptive Dark & White (Light) theme synchronization.
    """
    # ---------------------------------------------------------
    # 1. State Initialization
    # ---------------------------------------------------------
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []

    if "ai_chat_open" not in st.session_state:
        st.session_state.ai_chat_open = True

    if "ai_pending_prompt" not in st.session_state:
        st.session_state.ai_pending_prompt = None

    if "ai_selected_provider" not in st.session_state:
        st.session_state.ai_selected_provider = os.getenv("AI_PROVIDER", "gemini")

    if "app_theme" not in st.session_state:
        st.session_state.app_theme = "dark"

    is_dark = st.session_state.app_theme == "dark"
    db_status = get_database_status()

    # ---------------------------------------------------------
    # 2. Design Tokens for Dark & White Themes
    # ---------------------------------------------------------
    card_bg = "#111622" if is_dark else "#ffffff"
    card_border = "#2a3447" if is_dark else "#e2e8f0"
    card_shadow = "0 22px 64px rgba(0, 0, 0, 0.88), 0 0 0 1px rgba(255, 255, 255, 0.08)" if is_dark else "0 20px 50px rgba(0, 0, 0, 0.12), 0 2px 10px rgba(0, 0, 0, 0.06)"
    text_primary = "#f1f5f9" if is_dark else "#0f172a"
    text_secondary = "#94a3b8" if is_dark else "#64748b"
    text_strong = "#ffffff" if is_dark else "#0f172a"
    msg_bg = "rgba(255, 255, 255, 0.03)" if is_dark else "#f8fafc"
    msg_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#e2e8f0"
    avatar_bg = "#1e293b" if is_dark else "#f1f5f9"
    avatar_border = "#334155" if is_dark else "#cbd5e1"
    input_bg = "#1a2233" if is_dark else "#f8fafc"
    input_border = "#334155" if is_dark else "#cbd5e1"
    input_text = "#ffffff" if is_dark else "#0f172a"
    expander_bg = "#141c2e" if is_dark else "#f8fafc"
    expander_border = "#28354c" if is_dark else "#e2e8f0"
    expander_summary = "#38bdf8" if is_dark else "#0284c7"
    expander_details = "#e2e8f0" if is_dark else "#1e293b"
    chip_bg = "#1a2333" if is_dark else "#f1f5f9"
    chip_text = "#e2e8f0" if is_dark else "#1e293b"
    chip_border = "#2e3d55" if is_dark else "#e2e8f0"
    chip_hover_bg = "#233148" if is_dark else "#e2e8f0"
    chip_hover_text = "#38bdf8" if is_dark else "#0284c7"
    code_bg = "#0b0f19" if is_dark else "#f1f5f9"
    code_text = "#38bdf8" if is_dark else "#0369a1"
    code_border = "#1e293b" if is_dark else "#e2e8f0"
    table_bg = "#0d121d" if is_dark else "#ffffff"

    # ---------------------------------------------------------
    # 3. Inject Superset Copilot Design Tokens & Floating CSS
    # ---------------------------------------------------------
    st.html(f"""
    <style>
    /* ----------------------------------------------------- */
    /* Dynamic Font Inheritance from Parent Dashboard / Theme */
    /* ----------------------------------------------------- */
    div[class*="st-key-msu_superset_card"],
    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageContent"],
    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageContent"] *,
    div[class*="st-key-msu_superset_card"] [data-testid="stMarkdownContainer"],
    div[class*="st-key-msu_superset_card"] [data-testid="stMarkdownContainer"] *,
    div[class*="st-key-msu_superset_card"] button,
    div[class*="st-key-msu_superset_card"] input,
    div[class*="st-key-msu_superset_card"] textarea,
    div[class*="st-key-msu_superset_card"] p,
    div[class*="st-key-msu_superset_card"] label {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }}

    /* Protect Material Symbols & Emojis from font-family degradation */
    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageAvatar"],
    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageAvatar"] *,
    div[class*="st-key-msu_superset_card"] [data-testid="stIconMaterial"],
    div[class*="st-key-msu_superset_card"] .material-symbols-rounded,
    div[class*="st-key-msu_superset_card"] .material-symbols-sharp,
    div[class*="st-key-msu_superset_card"] .material-symbols-outlined,
    div[class*="st-key-msu_superset_card"] .material-icons {{
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons', sans-serif !important;
        font-size: 20px !important;
        line-height: 1 !important;
    }}

    /* Monospace strictly for numbers, tables, code blocks, and dataframes */
    div[class*="st-key-msu_superset_card"] code,
    div[class*="st-key-msu_superset_card"] pre,
    div[class*="st-key-msu_superset_card"] pre *,
    div[class*="st-key-msu_superset_card"] [data-testid="stDataFrame"],
    div[class*="st-key-msu_superset_card"] [data-testid="stDataFrame"] *,
    div[class*="st-key-msu_superset_card"] [data-testid="stTable"],
    div[class*="st-key-msu_superset_card"] [data-testid="stTable"] *,
    div[class*="st-key-msu_superset_card"] .stCodeBlock,
    div[class*="st-key-msu_superset_card"] .stCodeBlock * {{
        font-family: 'Roboto Mono', 'Fira Code', 'SF Mono', Consolas, monospace !important;
    }}

    /* ----------------------------------------------------- */
    /* 1. Floating Circular Sparkle Launcher (Bottom-Right)  */
    /* ----------------------------------------------------- */
    div[class*="st-key-msu_sparkle_launcher"] {{
        position: fixed !important;
        bottom: 22px !important;
        right: 26px !important;
        z-index: 9999999 !important;
        width: 54px !important;
        height: 54px !important;
    }}

    div[class*="st-key-msu_sparkle_launcher"] button {{
        width: 54px !important;
        height: 54px !important;
        border-radius: 50% !important;
        background: linear-gradient(135deg, #20a7c9 0%, #13829e 100%) !important;
        color: #ffffff !important;
        font-size: 22px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border: 2px solid rgba(255, 255, 255, 0.3) !important;
        box-shadow: 0 8px 26px rgba(32, 167, 201, 0.55), 0 2px 6px rgba(0, 0, 0, 0.4) !important;
        padding: 0 !important;
        cursor: pointer !important;
        transition: transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.2s ease !important;
    }}

    div[class*="st-key-msu_sparkle_launcher"] button:hover {{
        transform: scale(1.1) rotate(6deg) !important;
        box-shadow: 0 12px 34px rgba(32, 167, 201, 0.8) !important;
    }}

    /* ----------------------------------------------------- */
    /* 2. Floating Superset-Style Chat Card (Elevated Window)*/
    /* ----------------------------------------------------- */
    div[class*="st-key-msu_superset_card"] {{
        position: fixed !important;
        bottom: 88px !important;
        right: 26px !important;
        width: 490px !important;
        max-width: calc(100vw - 36px) !important;
        height: 640px !important;
        max-height: 84vh !important;
        z-index: 999999 !important;
        background: {card_bg} !important;
        border: 1px solid {card_border} !important;
        border-radius: 12px !important;
        box-shadow: {card_shadow} !important;
        padding: 12px 14px 12px 14px !important;
        display: flex !important;
        flex-direction: column !important;
        overflow-y: auto !important;
        animation: msuCardPop 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        color: {text_primary} !important;
        --text-color: {text_primary} !important;
        --primary-color: #20a7c9 !important;
        --background-color: {card_bg} !important;
        --secondary-background-color: {input_bg} !important;
    }}

    @keyframes msuCardPop {{
        from {{ opacity: 0; transform: translateY(18px) scale(0.96); }}
        to {{ opacity: 1; transform: translateY(0) scale(1); }}
    }}

    /* Text & Headings */
    div[class*="st-key-msu_superset_card"] p,
    div[class*="st-key-msu_superset_card"] span,
    div[class*="st-key-msu_superset_card"] div,
    div[class*="st-key-msu_superset_card"] li,
    div[class*="st-key-msu_superset_card"] label,
    div[class*="st-key-msu_superset_card"] [data-testid="stMarkdownContainer"] p,
    div[class*="st-key-msu_superset_card"] [data-testid="stMarkdownContainer"] span,
    div[class*="st-key-msu_superset_card"] [data-testid="stMarkdownContainer"] li {{
        color: {text_primary} !important;
        font-weight: 400 !important;
        letter-spacing: 0.01em !important;
    }}

    div[class*="st-key-msu_superset_card"] h1,
    div[class*="st-key-msu_superset_card"] h2,
    div[class*="st-key-msu_superset_card"] h3,
    div[class*="st-key-msu_superset_card"] h4,
    div[class*="st-key-msu_superset_card"] h5,
    div[class*="st-key-msu_superset_card"] h6,
    div[class*="st-key-msu_superset_card"] strong,
    div[class*="st-key-msu_superset_card"] b {{
        color: {text_strong} !important;
        font-weight: 600 !important;
    }}

    /* Chat message bubbles: clean row flex layout, zero text overlap */
    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessage"] {{
        display: flex !important;
        flex-direction: row !important;
        align-items: flex-start !important;
        gap: 12px !important;
        background-color: {msg_bg} !important;
        border: 1px solid {msg_border} !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        margin-bottom: 12px !important;
        width: 100% !important;
    }}

    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageAvatar"] {{
        width: 32px !important;
        min-width: 32px !important;
        max-width: 32px !important;
        height: 32px !important;
        border-radius: 50% !important;
        background: {avatar_bg} !important;
        border: 1px solid {avatar_border} !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        overflow: hidden !important;
        font-size: 16px !important;
        flex-shrink: 0 !important;
    }}

    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageContent"] {{
        flex: 1 1 auto !important;
        min-width: 0 !important;
        overflow-wrap: break-word !important;
        word-break: break-word !important;
    }}

    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageContent"] *,
    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageContent"] p,
    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageContent"] span,
    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageContent"] li,
    div[class*="st-key-msu_superset_card"] [data-testid="stChatMessageContent"] div {{
        color: {text_primary} !important;
        font-weight: 400 !important;
        font-size: 13px !important;
        line-height: 1.6 !important;
    }}

    /* Text Input Box */
    div[class*="st-key-msu_superset_card"] input[type="text"],
    div[class*="st-key-msu_superset_card"] input {{
        background-color: {input_bg} !important;
        color: {input_text} !important;
        border: 1px solid {input_border} !important;
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 400 !important;
    }}

    div[class*="st-key-msu_superset_card"] input::placeholder {{
        color: {text_secondary} !important;
        font-weight: 400 !important;
        opacity: 0.9 !important;
    }}

    div[class*="st-key-msu_superset_card"] input:focus {{
        border-color: #20a7c9 !important;
        box-shadow: 0 0 0 2px rgba(32, 167, 201, 0.25) !important;
        color: {input_text} !important;
    }}

    /* Send Button Solid Teal Styling */
    div[class*="st-key-msu_superset_card"] button[kind="primary"] {{
        background-color: #20a7c9 !important;
        border-color: #20a7c9 !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-radius: 4px !important;
        box-shadow: 0 2px 8px rgba(32, 167, 201, 0.4) !important;
    }}
    div[class*="st-key-msu_superset_card"] button[kind="primary"]:hover {{
        background-color: #1b8ea8 !important;
        border-color: #1b8ea8 !important;
    }}

    /* Expanders */
    div[class*="st-key-msu_superset_card"] [data-testid="stExpander"] {{
        background-color: {expander_bg} !important;
        border: 1px solid {expander_border} !important;
        border-radius: 8px !important;
        margin: 6px 0 !important;
    }}

    div[class*="st-key-msu_superset_card"] [data-testid="stExpander"] summary {{
        color: {expander_summary} !important;
        font-weight: 600 !important;
        font-size: 12px !important;
    }}

    div[class*="st-key-msu_superset_card"] [data-testid="stExpander"] summary svg {{
        fill: {expander_summary} !important;
    }}

    div[class*="st-key-msu_superset_card"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] * {{
        color: {expander_details} !important;
    }}

    /* Quick Preset Chips */
    div[class*="st-key-msu_superset_card"] button:not([kind="primary"]) {{
        background-color: {chip_bg} !important;
        color: {chip_text} !important;
        border: 1px solid {chip_border} !important;
        border-radius: 6px !important;
        font-size: 11px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
    }}

    div[class*="st-key-msu_superset_card"] button:not([kind="primary"]):hover {{
        background-color: {chip_hover_bg} !important;
        color: {chip_hover_text} !important;
        border-color: #20a7c9 !important;
    }}

    /* Engine Selectbox / Dropdown */
    div[class*="st-key-msu_superset_card"] [data-testid="stSelectbox"] div[data-baseweb="select"] {{
        background-color: {input_bg} !important;
        border-color: {input_border} !important;
    }}
    div[class*="st-key-msu_superset_card"] [data-testid="stSelectbox"] * {{
        color: {text_primary} !important;
    }}

    /* Dataframe / Tables */
    div[class*="st-key-msu_superset_card"] [data-testid="stDataFrame"] {{
        background-color: {table_bg} !important;
        border: 1px solid {card_border} !important;
        border-radius: 8px !important;
    }}

    /* Captions and Secondary Labels */
    div[class*="st-key-msu_superset_card"] [data-testid="stCaptionContainer"],
    div[class*="st-key-msu_superset_card"] .stCaption {{
        color: {text_secondary} !important;
    }}

    /* Code blocks and SQL */
    div[class*="st-key-msu_superset_card"] pre,
    div[class*="st-key-msu_superset_card"] code {{
        background-color: {code_bg} !important;
        color: {code_text} !important;
        border: 1px solid {code_border} !important;
        border-radius: 4px !important;
    }}

    @media (max-width: 768px) {{
        div[class*="st-key-msu_superset_card"] {{
            right: 8px !important;
            left: 8px !important;
            bottom: 80px !important;
            width: auto !important;
            max-width: 100vw !important;
            height: 86vh !important;
        }}
    }}
    </style>
    """)

    # ---------------------------------------------------------
    # 4. Sidebar Companion Controls & Theme Selection
    # ---------------------------------------------------------
    with st.sidebar:
        st.markdown("---")
        st.subheader("🤖 AI Data Analyst")

        theme_label = "☀️ Switch to White Theme" if is_dark else "🌙 Switch to Dark Theme"
        if st.button(theme_label, key="sidebar_theme_toggle_btn", use_container_width=True):
            st.session_state.app_theme = "light" if is_dark else "dark"
            st.rerun()

        if db_status.get("connected"):
            st.caption(f"🟢 **PostgreSQL Online** (`{db_status['database']}`)")
        else:
            st.caption("🟡 **Offline Local Rule Engine Active**")

        toggle_label = "✕ Hide Floating Copilot" if st.session_state.ai_chat_open else "💬 Open Floating Copilot"
        if st.button(toggle_label, key="sidebar_toggle_ai_chat", type="primary" if not st.session_state.ai_chat_open else "secondary", use_container_width=True):
            st.session_state.ai_chat_open = not st.session_state.ai_chat_open
            st.rerun()

        quick_query = st.text_input(
            "Quick Database Query",
            placeholder="e.g. Top courses, Device split...",
            key="sidebar_quick_query_input",
            label_visibility="collapsed"
        )
        if st.button("⚡ Ask Assistant", key="sidebar_run_quick_query", use_container_width=True):
            if quick_query and quick_query.strip():
                st.session_state.ai_pending_prompt = quick_query.strip()
                st.session_state.ai_chat_open = True
                st.rerun()

    # ---------------------------------------------------------
    # 5. Floating Circular Sparkle Button (Always Active in Corner)
    # ---------------------------------------------------------
    with st.container(key="msu_sparkle_launcher"):
        if st.button("✨", key="btn_sparkle_toggle", help="Toggle MSU AI Copilot"):
            st.session_state.ai_chat_open = not st.session_state.ai_chat_open
            st.rerun()

    if not st.session_state.ai_chat_open:
        return

    # ---------------------------------------------------------
    # 6. Floating Superset-Style Chat Card (When Open)
    # ---------------------------------------------------------
    with st.container(key="msu_superset_card"):
        # Header (ADMISSIONS V2 / SEO INTELLIGENCE Style)
        h_col1, h_col2, h_col3, h_col4 = st.columns([6.8, 1.1, 1.0, 1.1])
        with h_col1:
            title_color = "#f0f3f8" if is_dark else "#0f172a"
            sub_color = "#94a3b8" if is_dark else "#64748b"
            st.markdown(
                f"<div style='display: flex; align-items: center; gap: 8px; flex-wrap: nowrap;'>"
                f"<span style='font-size: 14px; font-weight: 700; color: {title_color}; white-space: nowrap;'>🤖 SEO INTELLIGENCE</span>"
                f"<span style='background: rgba(32,167,201,0.18); color: #20a7c9; border: 1px solid rgba(32,167,201,0.4); font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 3px; white-space: nowrap;'>LIVE</span>"
                f"<span style='color: {sub_color}; font-size: 11px; white-space: nowrap;'>Overview</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        with h_col2:
            theme_btn_label = "☀️" if is_dark else "🌙"
            theme_btn_help = "Switch to White/Light Theme" if is_dark else "Switch to Dark Theme"
            if st.button(theme_btn_label, key="superset_theme_toggle_btn", help=theme_btn_help, use_container_width=True):
                st.session_state.app_theme = "light" if is_dark else "dark"
                st.rerun()

        with h_col3:
            if st.button("🗑️", key="superset_clear_btn", help="Clear conversation memory", use_container_width=True):
                st.session_state.ai_messages = []
                st.session_state.ai_pending_prompt = None
                st.rerun()

        with h_col4:
            if st.button("✕", key="superset_close_btn", help="Close floating card", use_container_width=True):
                st.session_state.ai_chat_open = False
                st.rerun()

        # Sub-header bar: DB Status & Provider Selector
        s_col1, s_col2 = st.columns([5.5, 4.5])
        with s_col1:
            db_label = "🟢 PostgreSQL Online" if db_status.get("connected") else "🟡 Local Rules Active"
            st.markdown(f"<div style='font-size: 11px; color: {text_secondary}; padding-top: 6px;'>{db_label}</div>", unsafe_allow_html=True)

        with s_col2:
            provider_options = list(PROVIDERS_CONFIG.keys())
            provider_labels = [PROVIDERS_CONFIG[k]["name"] for k in provider_options]
            curr_prov = st.session_state.get("ai_selected_provider", os.getenv("AI_PROVIDER", "gemini"))
            prov_idx = provider_options.index(curr_prov) if curr_prov in provider_options else 0
            sel_prov_label = st.selectbox("Engine", options=provider_labels, index=prov_idx, key="superset_engine_select", label_visibility="collapsed")
            st.session_state.ai_selected_provider = provider_options[provider_labels.index(sel_prov_label)]

        # Chat Feed Container (Scrollable)
        feed_height = 360 if len(st.session_state.ai_messages) > 1 else 250
        chat_box = st.container(height=feed_height)

        with chat_box:
            if not st.session_state.ai_messages:
                st.info(
                    "👋 **MSU Admissions & SEO AI Copilot is active.**\n\n"
                    "Ask natural language questions on traffic, courses, blog readers, device drops, or conversions. "
                    "This widget stays floating here as you scroll through the dashboard."
                )
            else:
                for m_idx, msg in enumerate(st.session_state.ai_messages):
                    avatar = "👤" if msg["role"] == "user" else "🤖"
                    with st.chat_message(msg["role"], avatar=avatar):
                        # Render Primary Executive Narrative
                        content = msg["content"]
                        # Extract Summary vs Deep Dive sections
                        if "### 📌 Summary" in content:
                            parts = content.split("### 📌 Summary")
                            summary_section = parts[1].split("###")[0].strip() if len(parts) > 1 else content
                            summary_color = "#f8fafc" if is_dark else "#0f172a"
                            st.markdown(f"<div style='font-size: 13px; line-height: 1.6; color: {summary_color}; font-weight: 400; margin-bottom: 8px;'>{summary_section}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(content)

                        # Render Monospace Table Chart
                        df = msg.get("df")
                        if df is not None and not df.empty:
                            st.dataframe(df, use_container_width=True, height=min(180, 35 * (len(df) + 1)))

                        # Plotly Chart
                        if msg.get("chart") is not None:
                            st.plotly_chart(msg["chart"], use_container_width=True, key=f"superset_chart_{m_idx}")

                        # Deep Dive Collapsible Accordion (Strategic Root Causes & Playbook)
                        has_deep_dive = any(h in content for h in ["### 💡 Strategic Root Cause", "### 🎯 Leadership Action Playbook", "### 🔍 Quantitative Narrative"])
                        if has_deep_dive:
                            with st.expander("🔍 Know in Detail: Strategic Analysis & Playbook [DEEP DIVE]", expanded=False):
                                if "### 🔍 Quantitative Narrative & Findings" in content:
                                    st.markdown("#### 🔍 Quantitative Findings")
                                    q_part = content.split("### 🔍 Quantitative Narrative & Findings")[1].split("###")[0].strip()
                                    st.markdown(q_part)

                                if "### 💡 Strategic Root Cause" in content:
                                    st.markdown("#### 💡 Strategic Root Cause")
                                    r_part = content.split("### 💡 Strategic Root Cause")[1].split("###")[0].strip()
                                    st.markdown(r_part)

                                if "### 🎯 Leadership Action Playbook" in content:
                                    st.markdown("#### 🎯 Leadership Action Playbook")
                                    p_part = content.split("### 🎯 Leadership Action Playbook")[1].split("###")[0].strip()
                                    st.markdown(p_part)

                        # SQL Code Inspector Accordion
                        if msg.get("sql"):
                            with st.expander("🔍 View Executed SQL Query", expanded=False):
                                st.caption(f"⏱️ Executed in **{msg.get('execution_time_ms', 0):.1f} ms** | Retrieved **{len(df)} rows**")
                                st.code(msg["sql"], language="sql")
                                csv_data = df.to_csv(index=False).encode("utf-8")
                                st.download_button(
                                    "📥 Download CSV",
                                    data=csv_data,
                                    file_name=f"msu_query_turn_{m_idx}.csv",
                                    mime="text/csv",
                                    key=f"superset_dl_{m_idx}"
                                )

                        # Follow-Up Suggestion Pills
                        if msg.get("follow_ups"):
                            pill_color = "#38bdf8" if is_dark else "#0284c7"
                            st.markdown(f"<p style='font-size: 11px; font-weight: 600; margin-top: 6px; margin-bottom: 4px; color: {pill_color};'>💡 Suggested Next Inquiries:</p>", unsafe_allow_html=True)
                            for f_idx, q_text in enumerate(msg["follow_ups"][:3]):
                                if st.button(f"🔍 {q_text}", key=f"superset_pill_{m_idx}_{f_idx}", use_container_width=True):
                                    st.session_state.ai_pending_prompt = q_text
                                    st.rerun()

        # Preset Tag Grid (2x2 layout for full, untruncated button labels)
        lbl_color = "#94a3b8" if is_dark else "#64748b"
        st.markdown(f"<p style='font-size: 11px; font-weight: 600; margin: 4px 0 2px 0; color: {lbl_color};'>Quick Filters & Questions:</p>", unsafe_allow_html=True)
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            if st.button("📊 Top 10 Blogs", key="superset_tag_0", use_container_width=True):
                st.session_state.ai_pending_prompt = "Top 10 blog posts by views"
                st.rerun()
        with r1_c2:
            if st.button("🎓 Top 5 Courses", key="superset_tag_1", use_container_width=True):
                st.session_state.ai_pending_prompt = "Top 5 courses by views and active users"
                st.rerun()

        r2_c1, r2_c2 = st.columns(2)
        with r2_c1:
            if st.button("📱 Mobile vs Desktop", key="superset_tag_2", use_container_width=True):
                st.session_state.ai_pending_prompt = "Mobile vs Desktop traffic and conversion split"
                st.rerun()
        with r2_c2:
            if st.button("🔎 Low CTR Queries", key="superset_tag_3", use_container_width=True):
                st.session_state.ai_pending_prompt = "High-impression search queries with low CTR (<2%)"
                st.rerun()

        # Input Row (Solid Teal Send Button)
        with st.form("superset_chat_form", clear_on_submit=True):
            in_col, send_col = st.columns([5, 1])
            with in_col:
                user_text = st.text_input(
                    "Ask AI",
                    placeholder="Ask AI about traffic, blogs, courses, conversions...",
                    label_visibility="collapsed",
                    key="superset_form_input"
                )
            with send_col:
                submitted = st.form_submit_button("Send", type="primary", use_container_width=True)

        # Process Submission
        prompt_to_run = None
        if submitted and user_text and user_text.strip():
            prompt_to_run = user_text.strip()
        elif st.session_state.ai_pending_prompt:
            prompt_to_run = st.session_state.ai_pending_prompt
            st.session_state.ai_pending_prompt = None

        if prompt_to_run:
            # 1. Append user prompt
            st.session_state.ai_messages.append({"role": "user", "content": prompt_to_run})

            # 2. Execute with AI Analyst orchestrator (multi-turn context)
            with st.spinner("Analyzing PostgreSQL database..."):
                active_prov = st.session_state.get("ai_selected_provider", "gemini")
                active_key = st.session_state.get(f"{active_prov}_api_key")
                prov_cfg = PROVIDERS_CONFIG.get(active_prov, {})
                active_model = st.session_state.get("ai_selected_model", prov_cfg.get("default_model"))

                prior_history = [
                    {
                        "role": m["role"],
                        "content": m["content"],
                        "sql": m.get("sql", "")
                    }
                    for m in st.session_state.ai_messages[:-1]
                ]

                result = ask_ai_analyst(
                    prompt=prompt_to_run,
                    history=prior_history,
                    provider=active_prov,
                    api_key=active_key,
                    model=active_model,
                )

            # 3. Append response
            st.session_state.ai_messages.append({
                "role": "assistant",
                "content": result["answer"],
                "sql": result.get("sql"),
                "df": result.get("df"),
                "execution_time_ms": result.get("execution_time_ms", 0.0),
                "chart": result.get("chart"),
                "follow_ups": result.get("follow_ups", [])
            })

            # 4. Rerun with ai_chat_open = True
            st.session_state.ai_chat_open = True
            st.rerun()
