import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Traffic Snapshot - MSU Analytics",
    layout="wide",
    page_icon="🌐",
)

st.title("🌐 Latest Server Traffic Snapshot")
st.caption(
    "Granular breakdown of web requests, server-level access metrics, and external referrers."
)

# --- KEY PERFORMANCE METRICS ---
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Requests", "3,570", delta="Normal Volume")
m2.metric("Page Views", "3,570", delta="100% Rendered")
m3.metric("Unique IPs", "1,276", delta="Unique Visitors")
m4.metric("Bot Requests", "0", delta="Clean Traffic")
m5.metric("Error Count", "0", delta="0% 4xx/5xx")

st.divider()

# --- DATA PREPARATION ---
top_pages_data = [
    {"Page Path": "/", "Views": 1},
    {"Page Path": "/robots.txt", "Views": 1},
    {"Page Path": "/our-faculty", "Views": 1},
    {
        "Page Path": "/course/btech-in-cloud-computing-and-cyber-security",
        "Views": 1,
    },
    {
        "Page Path": "/blog/why-skill-based-education-is-important-in-this-era",
        "Views": 1,
    },
    {
        "Page Path": (
            "/events/hospitality-and-tourism-hosts-grooming-and-etiquette-workshop"
        ),
        "Views": 1,
    },
    {
        "Page Path": (
            "/events/hospitality-and-hotel-management-students-embark-on-ojt-journey"
        ),
        "Views": 1,
    },
    {
        "Page Path": (
            "/blog/unlocking-the-secrets-to-great-hospitality-a-hotel-management-perspective"
        ),
        "Views": 1,
    },
    {
        "Page Path": (
            "/events/halloween-at-medhavi-skills-university:-a-spooktacular-showcase-of-creativity-&-coordination"
        ),
        "Views": 1,
    },
    {
        "Page Path": (
            "/course/diploma-in-computer-science-engineering?utm_source=meta&utm_medium=paid&utm_campaign=cse_diploma"
        ),
        "Views": 1,
    },
]

top_referrers_data = [
    {"Referrer URL": "https://www.google.com/", "Visits": 405},
    {"Referrer URL": "https://international.msu.edu.in/", "Visits": 19},
    {"Referrer URL": "https://msu.edu.in/grievance-redressal", "Visits": 16},
    {"Referrer URL": "https://www.msu.edu.in/", "Visits": 15},
    {
        "Referrer URL": (
            "https://www.msu.edu.in/school/school-of-indigenous-knowledge-research-and-applications"
        ),
        "Visits": 12,
    },
    {"Referrer URL": "https://www.msu.edu.in/wise", "Visits": 11},
    {"Referrer URL": "http://msu.edu.in/wp-login.php", "Visits": 9},
    {
        "Referrer URL": (
            "http://www.msu.edu.in/school/school-of-indigenous-knowledge-research-application.html"
        ),
        "Visits": 8,
    },
    {
        "Referrer URL": (
            "android-app://com.google.android.googlequicksearchbox/"
        ),
        "Visits": 7,
    },
]

df_pages = pd.DataFrame(top_pages_data)
df_referrers = pd.DataFrame(top_referrers_data)

# --- DETAILED TABLES ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📄 Top Requested Pages")
    st.dataframe(
        df_pages,
        use_container_width=True,
        hide_index=True,
        column_config={"Views": st.column_config.NumberColumn("Page Views")},
    )

with col2:
    st.subheader("🔗 Top Referrers")
    st.dataframe(
        df_referrers,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Referrer URL": st.column_config.LinkColumn("Referrer Link"),
            "Visits": st.column_config.NumberColumn("Traffic Count"),
        },
    )

st.divider()

# --- REFERRER CHART ---
st.subheader("📈 Referral Source Breakdown")
fig_ref = px.bar(
    df_referrers.sort_values(by="Visits", ascending=True),
    x="Visits",
    y="Referrer URL",
    orientation="h",
    title="Inbound Traffic Volume by Origin",
    color="Visits",
    color_continuous_scale="Blues",
)
fig_ref.update_layout(height=400, margin=dict(l=20, r=20, t=40, b=20))
st.plotly_chart(fig_ref, use_container_width=True)