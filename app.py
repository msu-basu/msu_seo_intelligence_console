"""
MSU SEO Intelligence Console - Entry Point
Streamlit 1.36+ navigation API: hides the app.py item from sidebar.
Universal AI Assistant widget embedded across all views with dual Dark & White theme support.
"""
import streamlit as st
from src.ui.ai_widget import render_ai_widget

st.set_page_config(
    page_title="MSU SEO Intelligence Console",
    page_icon="favicon",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dual Theme State Management (Dark & White)
if "app_theme" not in st.session_state:
    st.session_state.app_theme = "dark"

is_dark = st.session_state.app_theme == "dark"

theme_css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"], .stApp {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background-color: {"#0b0f19" if is_dark else "#f8fafc"} !important;
    color: {"#f1f5f9" if is_dark else "#0f172a"} !important;
}}
div[data-testid="metric-container"] {{
    background: {"linear-gradient(135deg, #1e293b, #0f172a)" if is_dark else "#ffffff"} !important;
    border: 1px solid {"#334155" if is_dark else "#e2e8f0"} !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    box-shadow: {"0 4px 6px rgba(0,0,0,0.3)" if is_dark else "0 2px 8px rgba(0,0,0,0.06)"} !important;
}}
div[data-testid="metric-container"] label {{
    color: {"#94a3b8" if is_dark else "#64748b"} !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
}}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    color: {"#f1f5f9" if is_dark else "#0f172a"} !important;
    font-size: 24px !important;
    font-weight: 700 !important;
}}
</style>
"""
st.html(theme_css)

pg = st.navigation(
    {
        "Home": [
            st.Page("pages/00_Executive_Insights_Summary.py",
                    title="Executive Summary",              icon="📋"),
        ],
        "Analytics": [
            st.Page("pages/01_Executive_Dashboard.py",
                    title="Executive Dashboard",            icon="📈"),
            st.Page("pages/02_Blog_Intelligence.py",
                    title="Blog Intelligence",              icon="📝"),
            st.Page("pages/03_Course_Intelligence.py",
                    title="Course Intelligence",            icon="🎓"),
        ],
        "Deep Dives": [
            st.Page("pages/04_Device_Analysis.py",
                    title="Device Analysis",                icon="📱"),
            st.Page("pages/05_Geographic_Intelligence.py",
                    title="Geographic Intelligence",        icon="🌍"),
            st.Page("pages/06_Daily_Traffic_Report.py",
                    title="Daily Traffic Trends",           icon="📅"),
            st.Page("pages/07_SEO_Opportunities.py",
                    title="SEO Opportunities",              icon="🔎"),
            st.Page("pages/11_Regional_CTR_Intelligence.py",
                    title="Regional & CTR Intelligence",    icon="🗺️"),
        ],
        "Tools": [
            st.Page("pages/08_Data_Quality.py",
                    title="Data Quality",                   icon="✅"),
            st.Page("pages/09_Data_Export_Console.py",
                    title="Export Console",                 icon="📥"),
            st.Page("pages/10_Generate_HTML_Report.py",
                    title="Generate HTML Report",           icon="📄"),
        ],
    },
    position="sidebar",
)

# Render the universal AI Assistant widget (visible on EVERY view)
render_ai_widget()

pg.run()
