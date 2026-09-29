import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path

st.title("🔎 High-Impact SEO & Content Opportunities")
st.caption("Actionable bottlenecks derived from aggregated GA4 and GSC data.")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family:"Inter",sans-serif; }
</style>""", unsafe_allow_html=True)

from src.data.db_loader import load_file_or_db

DATA_DIR = Path("data/processed")

@st.cache_data
def agg_blog():
    df = load_file_or_db("01_Blog_GA4.parquet")
    if df.empty: return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    bad = {"/blog","/blog/","/","(not set)",""}
    for col in ["Views","Event count","Key events"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",","",regex=False),errors="coerce").fillna(0)
    agg_dict = {"Views":("Views","sum")}
    if "Event count" in df.columns: agg_dict["Event count"] = ("Event count","sum")
    if "Key events"  in df.columns: agg_dict["Key events"]  = ("Key events","sum")
    agg = df.groupby("Page path and screen class").agg(**agg_dict).reset_index()
    return agg[~agg["Page path and screen class"].isin(bad)]

@st.cache_data
def load_gsc(fname):
    df = load_file_or_db(fname)
    if df.empty: return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    for col in ["Clicks","Impressions","Position"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",","",regex=False),errors="coerce").fillna(0)
    if "CTR" in df.columns:
        df["CTR"] = pd.to_numeric(df["CTR"].astype(str).str.replace("%","",regex=False),errors="coerce").fillna(0)
    return df

blog_agg = agg_blog()
df_gsc   = load_gsc("gsc_blog_queries.parquet")

# ── 1. High Traffic, Zero Conversions ─────────────────────────────────────────
st.markdown("### 1. High-Traffic Articles with Zero Key Events")
st.caption("These pages get real visitors but fire no conversion events in GA4. Add CTAs here first.")

if not blog_agg.empty:
    if "Key events" in blog_agg.columns:
        bottlenecks = blog_agg[(blog_agg["Views"]>200) & (blog_agg["Key events"]==0)].copy()
    else:
        bottlenecks = blog_agg[blog_agg["Views"]>200].copy()
        st.info("No 'Key events' column found — showing all pages with >200 views. Enable CTA tracking in GA4.")

    if not bottlenecks.empty:
        bottlenecks["Sessions"] = (bottlenecks["Views"]/1.18).round().astype(int)
        bottlenecks = bottlenecks.sort_values("Views",ascending=False)
        st.warning(f"Found **{len(bottlenecks)}** high-traffic pages with zero conversion events.")
        show_cols = ["Page path and screen class","Views","Sessions"]
        if "Key events" in bottlenecks.columns: show_cols.append("Key events")
        st.dataframe(bottlenecks[show_cols].rename(
            columns={"Page path and screen class":"Page"}),
            hide_index=True, width="stretch",
            column_config={"Views":st.column_config.NumberColumn(format="%d"),
                           "Sessions":st.column_config.NumberColumn(format="%d")})
    else:
        st.success("No critical bottlenecks found.")
else:
    st.info("Add `01_Blog_GA4.parquet` to `data/input/` to detect bottlenecks.")

st.markdown("---")

# ── 2. Low CTR Opportunities ──────────────────────────────────────────────────
st.markdown("### 2. High-Impression Keywords with Low CTR (Title/Meta Opportunity)")
st.caption("These queries appear on Google but users don't click. Rewrite titles & meta descriptions.")

if not df_gsc.empty and "Impressions" in df_gsc.columns and "CTR" in df_gsc.columns:
    min_imp = st.slider("Minimum Impressions", 100, 10000, 500, step=100)
    max_ctr = st.slider("Max CTR (%)", 0.1, 5.0, 2.0, step=0.1)
    low_ctr = df_gsc[(df_gsc["Impressions"]>min_imp) & (df_gsc["CTR"]<max_ctr)].sort_values("Impressions",ascending=False)

    qcol = next((c for c in df_gsc.columns if "quer" in c.lower() or "top" in c.lower()), df_gsc.columns[0])
    if not low_ctr.empty:
        st.warning(f"**{len(low_ctr)}** keywords qualify. Showing top 20.")
        disp = low_ctr.rename(columns={qcol:"Search Query"})
        cols = ["Search Query","Impressions","Clicks","CTR","Position"]
        cols = [c for c in cols if c in disp.columns]
        st.dataframe(disp[cols].head(20), hide_index=True, width="stretch",
                     column_config={"Impressions":st.column_config.NumberColumn(format="%d"),
                                    "Clicks":st.column_config.NumberColumn(format="%d"),
                                    "CTR":st.column_config.NumberColumn("CTR (%)",format="%.2f%%"),
                                    "Position":st.column_config.NumberColumn(format="%.1f")})
        # Quick-win chart
        top20 = disp.rename(columns={qcol:"Search Query"})[cols].head(20)
        fig = px.bar(top20, x="Impressions", y="Search Query", orientation="h",
                     color="CTR", color_continuous_scale="RdYlGn",
                     title="High-Impression / Low-CTR Keywords")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#0f172a",
                          font_color="#f1f5f9", height=500,
                          yaxis=dict(autorange="reversed",gridcolor="#1e293b"),
                          xaxis=dict(gridcolor="#1e293b"),
                          margin=dict(l=10,r=10,t=40,b=10), coloraxis_showscale=True)
        st.plotly_chart(fig, width="stretch")
    else:
        st.success("No low-CTR opportunities found with current filters.")
else:
    st.info("Add `gsc_blog_queries.parquet` to `data/input/` for keyword intelligence.")

st.markdown("---")

# ── 3. Page 2 Keywords ────────────────────────────────────────────────────────
st.markdown("### 3. Page-2 Keywords — Striking Distance (Positions 10–20)")
st.caption("A few good internal links can push these to page 1.")

if not df_gsc.empty and "Position" in df_gsc.columns:
    qcol = next((c for c in df_gsc.columns if "quer" in c.lower() or "top" in c.lower()), df_gsc.columns[0])
    p2 = df_gsc[(df_gsc["Position"]>=10) & (df_gsc["Position"]<=20)].sort_values("Impressions",ascending=False)
    if not p2.empty:
        st.info(f"**{len(p2)}** keywords are on page 2 of Google.")
        disp = p2.rename(columns={qcol:"Search Query"})
        cols = ["Search Query","Position","Impressions","Clicks","CTR"]
        cols = [c for c in cols if c in disp.columns]
        st.dataframe(disp[cols].head(25), hide_index=True, width="stretch",
                     column_config={"Position":st.column_config.NumberColumn(format="%.1f"),
                                    "Impressions":st.column_config.NumberColumn(format="%d"),
                                    "CTR":st.column_config.NumberColumn("CTR (%)",format="%.2f%%")})
    else:
        st.success("No page-2 keywords found.")
else:
    st.info("GSC queries data not found.")
