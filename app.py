"""
MSU SEO Intelligence Console - Entry Point
Streamlit 1.36+ navigation API: hides the app.py item from sidebar.
"""
import streamlit as st

st.set_page_config(
    page_title="MSU SEO Intelligence Console",
    page_icon="favicon",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

pg.run()
