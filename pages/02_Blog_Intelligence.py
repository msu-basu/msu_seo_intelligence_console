import streamlit as st
import pandas as pd
import plotly.express as px
import re
from src.data.loaders import detect_and_load_all

st.set_page_config(page_title="Blog Intelligence", layout="wide")
st.title("📝 Blog Intelligence Console")
st.caption("Detailed readership analytics, category performance, and top-performing blog paths powered purely by GA4 data.")

# Load GA4 datasets
datasets = detect_and_load_all()
df_blog = datasets.get("blog", pd.DataFrame())

def clean_title(path):
    clean = re.sub(r"^/blog/|^/course/|/$|^/", "", str(path), flags=re.IGNORECASE)
    return clean.replace("-", " ").title()

def categorize_blog(path):
    p = str(path).lower()
    if any(kw in p for kw in ["career", "jobs", "salary", "scope", "placement"]):
        return "Career & Placement Guides"
    elif any(kw in p for kw in ["result", "exam", "cbse", "12th", "10th", "cutoff"]):
        return "Exams & Results"
    elif any(kw in p for kw in ["skills", "courses", "learn", "how-to"]):
        return "Skills & Course Guides"
    else:
        return "General Campus News"

if df_blog.empty:
    st.error("⚠️ No blog dataset found in `data/input/`. Please ensure your GA4 blog export is uploaded.")
else:
    # Dynamic column identification
    b_df = df_blog.copy()
    p_col = "Page path and screen class" if "Page path and screen class" in b_df.columns else b_df.columns[0]
    v_col = next((c for c in ["Views", "Event count"] if c in b_df.columns), b_df.columns[1])
    u_col = next((c for c in ["Active users", "Users"] if c in b_df.columns), b_df.columns[1])
    s_col = next((c for c in ["Sessions"] if c in b_df.columns), v_col)

    # Data transformation
    b_df = b_df[~b_df[p_col].isin(["/blog", "/blog/", "/", "(not set)"])].copy()
    b_df["Views"] = pd.to_numeric(b_df[v_col], errors='coerce').fillna(0)
    b_df["Active Users"] = pd.to_numeric(b_df[u_col], errors='coerce').fillna(0)
    b_df["Sessions"] = pd.to_numeric(b_df[s_col], errors='coerce').fillna(0)
    b_df["Category"] = b_df[p_col].apply(categorize_blog)
    b_df["Article Title"] = b_df[p_col].apply(clean_title)

    # Top-level KPI metrics
    tot_views = int(b_df["Views"].sum())
    tot_articles = b_df["Article Title"].nunique()
    tot_users = int(b_df["Active Users"].sum())
    avg_views = int(tot_views / tot_articles) if tot_articles > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Blog Articles", f"{tot_articles:,}")
    col2.metric("Total Blog Views", f"{tot_views:,}")
    col3.metric("Active Readers", f"{tot_users:,}")
    col4.metric("Avg Views / Article", f"{avg_views:,}")

    st.markdown("---")

    # Category and Top 10 Charts
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📊 Views Share by Category")
        cat_df = b_df.groupby("Category")["Views"].sum().reset_index()
        fig_cat = px.pie(
            cat_df,
            values="Views",
            names="Category",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    with c2:
        st.subheader("🏆 Top 10 Most Read Blog Articles")
        top10_df = b_df.groupby("Article Title")["Views"].sum().reset_index().sort_values(by="Views", ascending=True).tail(10)
        fig_top = px.bar(
            top10_df,
            x="Views",
            y="Article Title",
            orientation="h",
            color_discrete_sequence=["#2563eb"]
        )
        st.plotly_chart(fig_top, use_container_width=True)

    st.markdown("---")

    # Chart 7: Replaced with GA4 Organic Blog Paths
    st.subheader("📊 Chart 7: Top Blog Paths by Organic Views (GA4)")
    top_paths = b_df.groupby(p_col)["Views"].sum().reset_index().sort_values(by="Views", ascending=True).tail(10)
    
    fig_chart7 = px.bar(
        top_paths,
        x="Views",
        y=p_col,
        orientation="h",
        title="Top 10 Most Visited Blog URL Paths",
        color_discrete_sequence=["#0d9488"]
    )
    fig_chart7.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_chart7, use_container_width=True)

    st.markdown("---")

    # Interactive Directory Table
    st.subheader("📋 Blog Directory Metrics")
    summary_table = b_df.groupby(["Article Title", "Category"])[["Views", "Sessions", "Active Users"]].sum().reset_index().sort_values(by="Views", ascending=False)
    
    search_term = st.text_input("🔍 Search Blog Articles by Title or Category:")
    if search_term:
        summary_table = summary_table[
            summary_table["Article Title"].str.contains(search_term, case=False, na=False) |
            summary_table["Category"].str.contains(search_term, case=False, na=False)
        ]

    st.dataframe(summary_table, use_container_width=True, hide_index=True)