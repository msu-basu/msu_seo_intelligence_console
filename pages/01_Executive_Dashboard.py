import streamlit as st
import pandas as pd
from src.data.loaders import detect_and_load_all
from src.ui.charts import plot_pie_chart

st.set_page_config(page_title="Executive Dashboard", layout="wide")
st.title("📊 Executive Performance Dashboard & BI Analytics")
st.caption("High-level executive KPIs, automated metric fallbacks, and content share intelligence.")

datasets = detect_and_load_all()

df_base = datasets.get("baseline", pd.DataFrame())
df_blog = datasets.get("blog", pd.DataFrame())
df_course = datasets.get("course", pd.DataFrame())
df_device = datasets.get("device", pd.DataFrame())

def safe_sum(df, candidate_cols):
    if df.empty:
        return 0
    for col in candidate_cols:
        if col in df.columns:
            return pd.to_numeric(df[col], errors='coerce').fillna(0).sum()
    return 0

# Extract individual totals
blog_views = safe_sum(df_blog, ["Views", "Event count"])
course_views = safe_sum(df_course, ["Views", "Event count"])
total_conversions = safe_sum(df_base, ["Key events", "Conversions"]) + safe_sum(df_blog, ["Key events"])

# Compute Total Views with smart fallback
total_views = safe_sum(df_base, ["Views", "Event count", "Screen views"])
if total_views == 0:
    total_views = blog_views + course_views

total_users = safe_sum(df_base, ["Active users", "Users"])
if total_users == 0:
    total_users = max(safe_sum(df_blog, ["Active users"]), safe_sum(df_device, ["Active users"]))

# --- Executive Top KPIs ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Web Views", f"{int(total_views):,}")
m2.metric("Active Users", f"{int(total_users):,}")
m3.metric("Key Events (Conversions)", f"{int(total_conversions):,}")
m4.metric("Blog Article Views", f"{int(blog_views):,}")

st.markdown("---")

# --- BI Analytics Executive Layer ---
st.subheader("💡 Automated BI Executive Insights")
b1, b2, b3 = st.columns(3)

blog_share = (blog_views / total_views * 100) if total_views > 0 else 0
course_share = (course_views / total_views * 100) if total_views > 0 else 0
conv_rate = (total_conversions / total_users * 100) if total_users > 0 else 0

with b1:
    st.info(f"**Blog Traffic Share: {blog_share:.1f}%**\n\nBlog content accounts for **{blog_share:.1f}%** of total measured session volume.")

with b2:
    st.success(f"**Course Intent Share: {course_share:.1f}%**\n\nAcademic catalog pages drive **{course_share:.1f}%** of active user interest.")

with b3:
    st.warning(f"**Conversion Efficiency: {conv_rate:.2f}%**\n\nKey event completion rate per active user session.")

st.markdown("---")

# Visual Layout
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Top Performing Content")
    if not df_blog.empty:
        page_col = "Page path and screen class" if "Page path and screen class" in df_blog.columns else df_blog.columns[0]
        views_col = "Views" if "Views" in df_blog.columns else df_blog.columns[1]
        top_blogs = df_blog.sort_values(by=views_col, ascending=False).head(5)
        st.dataframe(top_blogs[[page_col, views_col]], width="stretch")

with col_right:
    st.subheader("Traffic Share by Device")
    if not df_device.empty:
        dev_col = "Device category" if "Device category" in df_device.columns else df_device.columns[0]
        val_col = "Active users" if "Active users" in df_device.columns else df_device.columns[1]
        fig = plot_pie_chart(df_device, values=val_col, names=dev_col, title="Device Share")
        if fig:
            st.plotly_chart(fig, width="stretch")