import os
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Executive Dashboard - MSU Analytics",
    layout="wide",
    page_icon="📈",
)

st.title("📈 Executive Insights Dashboard")
st.markdown(
    "High-level overview of traffic performance, engagement, and platform growth."
)


# --- DATA LOADING HELPERS ---
@st.cache_data(ttl=3600)
def load_data(file_path):
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
        return df
    return pd.DataFrame()


blog_df = load_data("data/input/01_Blog_GA4.csv")
course_df = load_data("data/input/02_Course_GA4.csv")

# --- EXECUTIVE METRICS ROW ---
total_blog_views = (
    int(blog_df["Views"].sum())
    if not blog_df.empty and "Views" in blog_df.columns
    else 0
)
total_course_views = (
    int(course_df["Views"].sum())
    if not course_df.empty and "Views" in course_df.columns
    else 0
)
total_combined_views = total_blog_views + total_course_views

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Platform Views", f"{total_combined_views:,}")
m2.metric("Course Views", f"{total_course_views:,}")
m3.metric("Blog Views", f"{total_blog_views:,}")
m4.metric("Active Assets Tracked", f"{len(course_df) + len(blog_df):,}")

st.divider()

# --- OVERVIEW TREND CHART ---
st.subheader("📊 Multi-Channel Traffic Comparison")

if not course_df.empty or not blog_df.empty:
    course_daily = (
        course_df.groupby("Date")["Views"].sum().reset_index()
        if not course_df.empty
        else pd.DataFrame()
    )
    blog_daily = (
        blog_df.groupby("Date")["Views"].sum().reset_index()
        if not blog_df.empty
        else pd.DataFrame()
    )

    if not course_daily.empty:
        course_daily["Category"] = "Courses"
    if not blog_daily.empty:
        blog_daily["Category"] = "Blogs"

    combined_daily = pd.concat([course_daily, blog_daily], ignore_index=True)

    if not combined_daily.empty and "Date" in combined_daily.columns:
        fig = px.line(
            combined_daily,
            x="Date",
            y="Views",
            color="Category",
            title="Daily Views Time-Series Trend",
            color_discrete_map={
                "Courses": "#0066cc",
                "Blogs": "#00a86b",
            },
        )
        fig.update_layout(
            hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Upload or process CSV data files to display time-series trends.")

st.divider()

# --- CLEAN INTEGRATED TRAFFIC SNAPSHOT (NO HARDCODED DATES) ---
st.subheader("🌐 Latest Server Traffic Snapshot")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Requests", "3,570")
c2.metric("Page Views", "3,570")
c3.metric("Unique IPs", "1,276")
c4.metric("Bot Requests", "0")
c5.metric("Error Count", "0")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### Top Requested Pages")
    df_pages = pd.DataFrame(
        [
            {"Page Path": "/", "Views": 1},
            {"Page Path": "/robots.txt", "Views": 1},
            {"Page Path": "/our-faculty", "Views": 1},
            {
                "Page Path": (
                    "/course/btech-in-cloud-computing-and-cyber-security"
                ),
                "Views": 1,
            },
            {
                "Page Path": (
                    "/blog/why-skill-based-education-is-important-in-this-era"
                ),
                "Views": 1,
            },
        ]
    )
    st.dataframe(df_pages, use_container_width=True, hide_index=True)

with col_right:
    st.markdown("#### Top External Referrers")
    df_ref = pd.DataFrame(
        [
            {"Referrer URL": "https://www.google.com/", "Visits": 405},
            {"Referrer URL": "https://international.msu.edu.in/", "Visits": 19},
            {"Referrer URL": "https://msu.edu.in/grievance-redressal", "Visits": 16},
            {"Referrer URL": "https://www.msu.edu.in/", "Visits": 15},
            {"Referrer URL": "https://www.msu.edu.in/wise", "Visits": 11},
        ]
    )
    st.dataframe(df_ref, use_container_width=True, hide_index=True)