import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

st.title("📈 Executive Dashboard")
st.caption("Multi-channel traffic overview — aggregated from GA4 daily exports.")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family:"Inter",sans-serif; }
div[data-testid="metric-container"] {
    background:linear-gradient(135deg,#1e293b,#0f172a);
    border:1px solid #334155; border-radius:12px; padding:16px 20px;
}
div[data-testid="metric-container"] label { color:#94a3b8!important; font-size:11px!important; text-transform:uppercase; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#f1f5f9!important; font-size:24px!important; font-weight:700!important; }
</style>""", unsafe_allow_html=True)

from src.data.db_loader import load_file_or_db

DATA_DIR = Path("data/processed")

@st.cache_data
def load_daily(fname):
    df = load_file_or_db(fname)
    if df.empty: return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    if "Views" in df.columns:
        df["Views"] = pd.to_numeric(df["Views"].astype(str).str.replace(",","",regex=False), errors="coerce").fillna(0)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df

@st.cache_data
def agg_to_page(df, path_col="Page path and screen class"):
    bad = {"/blog","/blog/","/courses","/courses/","/","(not set)",""}
    a = df.groupby(path_col).agg(Views=("Views","sum"), AU=("Active users","max")).reset_index()
    return a[~a[path_col].isin(bad)]

from src.data.db_loader import load_page_summary_from_db

# ── Page Aggregates (Loaded in ~50ms from PostgreSQL Views) ───────────────────
blog_agg = load_page_summary_from_db("blog")
if blog_agg.empty:
    blog_raw = load_daily("01_Blog_GA4.parquet")
    blog_agg = agg_to_page(blog_raw) if not blog_raw.empty else pd.DataFrame()

course_agg_p = load_page_summary_from_db("course")
if course_agg_p.empty:
    course_raw = load_daily("02_Course_GA4.parquet")
    course_agg_p = agg_to_page(course_raw) if not course_raw.empty else pd.DataFrame()
if not course_agg_p.empty and "Page path and screen class" in course_agg_p.columns:
    course_agg_p = course_agg_p[course_agg_p["Page path and screen class"].str.contains(r"/course", case=False, na=False)]

blog_views   = int(blog_agg["Views"].sum())     if not blog_agg.empty   else 0
course_views = int(course_agg_p["Views"].sum()) if not course_agg_p.empty else 0
blog_articles = len(blog_agg)
course_pages  = len(course_agg_p)
combined_views = blog_views + course_views

# ── KPIs ──────────────────────────────────────────────────────────────────────
m1,m2,m3,m4 = st.columns(4)
m1.metric("Total Platform Views",  f"{combined_views:,}", help="Blog + Course — aggregated to page grain")
m2.metric("Blog Views",            f"{blog_views:,}")
m3.metric("Course Views",          f"{course_views:,}")
m4.metric("Unique Pages Tracked",  f"{blog_articles + course_pages:,}", help="Articles + course pages (not raw rows)")

st.markdown("---")

# ── Daily Trend ───────────────────────────────────────────────────────────────
st.markdown("### Daily Views Time-Series Trend")

from src.data.db_loader import load_daily_traffic_from_db

combined = load_daily_traffic_from_db()
if combined.empty:
    blog_raw = load_daily("01_Blog_GA4.parquet")
    course_raw = load_daily("02_Course_GA4.parquet")
    frames = []
    if not blog_raw.empty and "Date" in blog_raw.columns:
        bd = blog_raw.groupby("Date")["Views"].sum().reset_index()
        bd["Channel"] = "Blog"
        frames.append(bd)
    if not course_raw.empty and "Date" in course_raw.columns:
        cd = course_raw.groupby("Date")["Views"].sum().reset_index()
        cd["Channel"] = "Courses"
        frames.append(cd)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

if not combined.empty:
    fig = px.line(combined, x="Date", y="Views", color="Channel",
                  color_discrete_map={"Blog":"#38bdf8","Courses":"#a78bfa"},
                  labels={"Views":"Daily Views","Date":""},
                  template="plotly_dark")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                      font_color="#f1f5f9", hovermode="x unified",
                      legend=dict(orientation="h",y=1.02), height=380,
                      margin=dict(l=20,r=20,t=20,b=20),
                      xaxis=dict(gridcolor="#1e293b"), yaxis=dict(gridcolor="#1e293b"))
    st.plotly_chart(fig, width="stretch")
else:
    st.info("No CSV data found in `data/input/`. Add `01_Blog_GA4.parquet` and `02_Course_GA4.parquet`.")

st.markdown("---")

# ── Top Pages by Total Views ───────────────────────────────────────────────────
st.markdown("### Top 10 Pages by Total Views (Period)")
col_b, col_c = st.columns(2)

with col_b:
    st.caption("Blog Articles")
    if not blog_agg.empty:
        au_b = "AU" if "AU" in blog_agg.columns else ("Active users" if "Active users" in blog_agg.columns else blog_agg.columns[1])
        top_b = blog_agg.nlargest(10, "Views")[["Page path and screen class", "Views", au_b]].rename(
            columns={"Page path and screen class": "Page", au_b: "Active Users"})
        st.dataframe(top_b, hide_index=True, width="stretch",
                     column_config={"Views": st.column_config.NumberColumn(format="%d"),
                                    "Active Users": st.column_config.NumberColumn(format="%d")})
    else:
        st.info("No blog data found.")

with col_c:
    st.caption("Course Pages")
    if not course_agg_p.empty:
        au_c = "AU" if "AU" in course_agg_p.columns else ("Active users" if "Active users" in course_agg_p.columns else course_agg_p.columns[1])
        top_c = course_agg_p.nlargest(10, "Views")[["Page path and screen class", "Views", au_c]].rename(
            columns={"Page path and screen class": "Page", au_c: "Active Users"})
        st.dataframe(top_c, hide_index=True, width="stretch",
                     column_config={"Views": st.column_config.NumberColumn(format="%d"),
                                    "Active Users": st.column_config.NumberColumn(format="%d")})
    else:
        st.info("No course data found.")
