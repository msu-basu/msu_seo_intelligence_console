import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

st.title("📋 Executive Analytics & SEO Insights Summary")
st.caption("Single-page command centre aggregating Blog, Course, Search Console and Device data.")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: "Inter", sans-serif; }
div[data-testid="metric-container"] {
    background: linear-gradient(135deg,#1e293b,#0f172a);
    border:1px solid #334155; border-radius:12px; padding:16px 20px;
}
div[data-testid="metric-container"] label { color:#94a3b8!important; font-size:11px!important; text-transform:uppercase; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#f1f5f9!important; font-size:24px!important; font-weight:700!important; }
</style>""", unsafe_allow_html=True)

from src.data.db_loader import load_file_or_db, load_page_summary_from_db

DATA_DIR = Path("data/processed")

@st.cache_data
def load_agg_blog():
    df_view = load_page_summary_from_db("blog")
    if not df_view.empty:
        return df_view
    df = load_file_or_db("01_Blog_GA4.parquet")
    if df.empty: return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    bad = {"/blog","/blog/","/","(not set)",""}
    agg = df.groupby("Page path and screen class").agg(
        Views=("Views","sum"), AU=("Active users","max"),
        Events=("Event count","sum"), KE=("Key events","sum")
    ).reset_index()
    agg = agg[~agg["Page path and screen class"].isin(bad)]
    return agg

@st.cache_data
def load_agg_course():
    df_view = load_page_summary_from_db("course")
    if not df_view.empty:
        return df_view
    df = load_file_or_db("02_Course_GA4.parquet")
    if df.empty: return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    bad = {"/","/courses","/courses/","(not set)",""}
    agg = df.groupby("Page path and screen class").agg(
        Views=("Views","sum"), AU=("Active users","max"),
        Events=("Event count","sum")
    ).reset_index()
    agg = agg[~agg["Page path and screen class"].isin(bad)]
    import re
    agg = agg[agg["Page path and screen class"].str.contains(r"/course",case=False,na=False)]
    return agg

@st.cache_data
def load_gsc_queries():
    for fname in ["gsc_blog_queries.parquet","gsc_course_queries.parquet"]:
        df = load_file_or_db(fname)
        if not df.empty:
            df.columns = [c.strip() for c in df.columns]
            for col in ["Clicks","Impressions","Position"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(",","",regex=False), errors="coerce").fillna(0)
            if "CTR" in df.columns:
                df["CTR"] = pd.to_numeric(df["CTR"].astype(str).str.replace("%","",regex=False), errors="coerce").fillna(0)
            return df
    return pd.DataFrame()

blog_agg   = load_agg_blog()
course_agg = load_agg_course()
df_gsc     = load_gsc_queries()

blog_views    = int(blog_agg["Views"].sum())   if not blog_agg.empty   else 0
course_views  = int(course_agg["Views"].sum()) if not course_agg.empty else 0
blog_sessions = int(blog_views / 1.18)
gsc_clicks    = int(df_gsc["Clicks"].sum())      if not df_gsc.empty and "Clicks" in df_gsc.columns else 0
gsc_imp       = int(df_gsc["Impressions"].sum())  if not df_gsc.empty and "Impressions" in df_gsc.columns else 0
n_articles    = len(blog_agg)
n_courses     = len(course_agg)

# ── KPIs ────────────────────────────────────────────────────────────────────
st.markdown("### Platform-Wide KPIs")
k1,k2,k3,k4,k5,k6 = st.columns(6)
k1.metric("Blog Articles",          f"{n_articles:,}")
k2.metric("Blog Views",             f"{blog_views:,}")
k3.metric("Est. Blog Sessions",     f"{blog_sessions:,}", help="Views / 1.18")
k4.metric("Course Pages",           f"{n_courses:,}")
k5.metric("Organic Search Clicks",  f"{gsc_clicks:,}")
k6.metric("Search Impressions",     f"{gsc_imp:,}")

st.markdown("---")

# ── Category Breakdown ───────────────────────────────────────────────────────
st.markdown("### Blog Category Performance")

import re as _re
def _cat(path):
    p = str(path).lower()
    if any(k in p for k in ["career","jobs","salary","scope","placement"]): return "Career & Placement"
    if any(k in p for k in ["result","exam","cbse","12th","10th","cutoff"]):  return "Exams & Results"
    if any(k in p for k in ["skills","courses","learn","how-to","paramedical"]): return "Skills & Courses"
    return "General Campus"

if not blog_agg.empty:
    blog_agg["Category"] = blog_agg["Page path and screen class"].apply(_cat)
    cat_s = blog_agg.groupby("Category")["Views"].sum().reset_index().sort_values("Views", ascending=False)
    top_cat = cat_s.iloc[0]
    top_pct = top_cat["Views"] / cat_s["Views"].sum() * 100

    cc1, cc2 = st.columns([1,2])
    with cc1:
        fig_pie = px.pie(cat_s, values="Views", names="Category", hole=0.45,
                         color_discrete_sequence=px.colors.qualitative.Bold)
        fig_pie.update_traces(textinfo="percent+label")
        fig_pie.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                              font_color="#f1f5f9", height=300, margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig_pie, width="stretch")
    with cc2:
        st.markdown(f"""
**Key Insights (from your data):**
- **Total Blog Articles Tracked:** {n_articles:,} unique pages
- **Top Category:** {top_cat["Category"]} — **{top_pct:.1f}%** of total views ({int(top_cat["Views"]):,} views)
- **Search Visibility:** {gsc_imp:,} impressions, {gsc_clicks:,} organic clicks
- **Est. Sessions:** {blog_sessions:,} (derived from Views ÷ 1.18)
""")
        st.dataframe(cat_s.rename(columns={"Views":"Total Views"}), hide_index=True, width="stretch")

st.markdown("---")

# ── SEO Action Table ─────────────────────────────────────────────────────────
st.markdown("### Priority Action Items for the SEO Team")

low_ctr_cnt = 0
if not df_gsc.empty and "CTR" in df_gsc.columns and "Impressions" in df_gsc.columns:
    low_ctr_cnt = len(df_gsc[(df_gsc["Impressions"]>500) & (df_gsc["CTR"]<2.0)])

p2_cnt = 0
if not df_gsc.empty and "Position" in df_gsc.columns:
    p2_cnt = len(df_gsc[(df_gsc["Position"]>=10) & (df_gsc["Position"]<=20)])

st.markdown(f"""
| Priority | Channel | Data-Driven Finding | Required Action |
|---|---|---|---|
| **P1 High** | Blog | **{low_ctr_cnt}** queries with >500 impressions but <2% CTR | Rewrite page titles & meta descriptions |
| **P1 High** | Courses | Top course pages with high views, zero lead events | Embed WhatsApp inquiry CTAs + PDF brochures |
| **P2 Medium** | SEO | **{p2_cnt}** keywords on positions 10–20 (page 2) | Add internal links from top blog posts |
| **P3 Optimise** | Technical | Check device split on Page 04 | Optimise mobile speed & form UX |
""")
