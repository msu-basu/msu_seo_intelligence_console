import streamlit as st
import pandas as pd
from src.data.loaders import detect_and_load_all
from src.ui.tables import render_table_with_download

st.set_page_config(page_title="SEO Opportunities", layout="wide")
st.title("🎯 High-Impact SEO & Content Opportunities")
st.caption("Actionable bottlenecks derived from your performance data.")

datasets = detect_and_load_all()

# Load Datasets
df_blog = datasets.get("blog", pd.DataFrame())
df_gsc = datasets.get("gsc_queries", pd.DataFrame())

# --- GA4 OPPORTUNITY 1: High Traffic, Low/Zero Conversions ---
st.subheader("1. High Traffic Pages with Zero Key Events (Conversion Bottlenecks)")

if not df_blog.empty:
    page_col = "Page path and screen class" if "Page path and screen class" in df_blog.columns else df_blog.columns[0]
    views_col = "Views" if "Views" in df_blog.columns else "Views"
    events_col = "Key events" if "Key events" in df_blog.columns else None

    if views_col in df_blog.columns:
        if events_col and events_col in df_blog.columns:
            bottlenecks = df_blog[(df_blog[views_col] > 100) & (df_blog[events_col].fillna(0) == 0)]
        else:
            bottlenecks = df_blog.sort_values(by=views_col, ascending=False).head(10)

        if not bottlenecks.empty:
            st.warning(f"Found {len(bottlenecks)} high-traffic pages producing zero conversions. Add CTAs or lead forms here first.")
            display_cols = [c for c in [page_col, views_col, events_col] if c and c in bottlenecks.columns]
            st.dataframe(bottlenecks[display_cols].head(10), width="stretch")
        else:
            st.success("No critical high-traffic zero-conversion bottlenecks found.")
else:
    st.info("💡 Upload `01_Blog_GA4.csv` to detect high-traffic conversion bottlenecks.")

# --- GSC OPPORTUNITIES: Render ONLY if GSC data exists ---
if not df_gsc.empty and "Impressions" in df_gsc.columns:
    st.markdown("---")
    st.subheader("2. High Impression Terms with Low CTR (Title/Meta Opportunity)")
    
    if "CTR" not in df_gsc.columns and "Clicks" in df_gsc.columns:
        df_gsc["CTR"] = (df_gsc["Clicks"] / df_gsc["Impressions"]) * 100

    if "CTR" in df_gsc.columns:
        low_ctr = df_gsc[(df_gsc["Impressions"] > 500) & (df_gsc["CTR"] < 2.0)].sort_values(by="Impressions", ascending=False)
        if not low_ctr.empty:
            st.write("These keywords get search impressions but low clicks. Rewrite page titles and meta descriptions:")
            render_table_with_download(low_ctr.head(10), filename="low_ctr_keywords.csv", key="low_ctr")
        else:
            st.info("No low-CTR keyword bottlenecks detected.")

    st.markdown("---")
    st.subheader("3. Low Hanging Fruit Keywords (Positions 10-20)")
    if "Position" in df_gsc.columns:
        striking_distance = df_gsc[(df_gsc["Position"] >= 10) & (df_gsc["Position"] <= 20)].sort_values(by="Impressions", ascending=False)
        if not striking_distance.empty:
            st.write("Keywords sitting on page 2 of Google. Target these with internal links and content updates:")
            render_table_with_download(striking_distance.head(10), filename="page2_keywords.csv", key="page2_kw")
        else:
            st.info("No position 10-20 opportunities detected.")