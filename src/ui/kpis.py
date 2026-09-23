import streamlit as st
from src.utils.formatting import format_number, format_percent

def render_executive_kpis(summary: dict):
    """Renders top-level KPI metrics cards."""
    col1, col2, col3, col4, col5 = st.columns(5)
    
    col1.metric("Sessions", format_number(summary.get("sessions", 0)))
    col2.metric("Active Users", format_number(summary.get("users", 0)))
    col3.metric("Page Views", format_number(summary.get("views", 0)))
    col4.metric("Key Events (Leads)", format_number(summary.get("key_events", 0)))
    col5.metric("Search Clicks", format_number(summary.get("gsc_clicks", 0)))