import streamlit as st

st.set_page_config(layout="wide")

pages = [
    st.Page("pages/00_Executive_Insights_Summary.py", title="Executive Insights Summary", icon="📌"),
    st.Page("pages/01_Executive_Dashboard.py", title="Executive Dashboard", icon="📊"),
    st.Page("pages/02_Blog_Intelligence.py", title="Blog Intelligence", icon="📝"),
    st.Page("pages/03_Course_Intelligence.py", title="Course Intelligence", icon="🎓"),
    st.Page("pages/04_Device_Analysis.py", title="Device Analysis", icon="📱"),
    st.Page("pages/05_SEO_Opportunities.py", title="SEO Opportunities", icon="🎯"),
    st.Page("pages/06_Data_Quality.py", title="Data Quality", icon="🧹"),
    st.Page("pages/07_Data_Export_Console.py", title="Data Export Console", icon="📥"),
    st.Page("pages/08_Generate_HTML_Report.py", title="Generate HTML Report", icon="📄"),
]

pg = st.navigation(pages)
pg.run()