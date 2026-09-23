import streamlit as st
import pandas as pd
import plotly.express as px
import re
from src.data.loaders import detect_and_load_all

st.set_page_config(page_title="Course Intelligence", layout="wide")
st.title("🎓 Academic Course Intelligence & Demand Analytics")
st.caption("Granular tracking across ~42–100 individual course URLs, degree level categorizations, daily time-series trends, device attribution, and Google search queries.")

datasets = detect_and_load_all()
df_course = datasets.get("course", pd.DataFrame())
df_gsc = datasets.get("gsc_queries", pd.DataFrame())
df_device = datasets.get("device", pd.DataFrame())

def clean_course_name(path):
    if not isinstance(path, str) or not path:
        return "Unknown Program"
    clean = re.sub(r"^/course/|/$|^/", "", str(path), flags=re.IGNORECASE)
    clean = clean.replace("-", " ")
    clean = re.sub(r"\bbtech\b", "B.Tech", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bmsc\b|\bm-sc\b", "M.Sc", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bbsc\b|\bb-sc\b", "B.Sc", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bphd\b", "Ph.D.", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bdoctor of philosophy\b", "Ph.D.", clean, flags=re.IGNORECASE)
    return clean.title()

def categorize_program_level(path):
    p = str(path).lower()
    if any(kw in p for kw in ["bachelor", "btech", "b-tech", "b-sc", "bca", "bba", "bcom", "b-pharm", "ug"]):
        return "Bachelor (Undergraduate)"
    elif any(kw in p for kw in ["master", "mtech", "m-tech", "m-sc", "mca", "mba", "mcom", "m-pharm", "pg"]):
        return "Master (Postgraduate)"
    elif "diploma" in p:
        return "Diploma"
    elif any(kw in p for kw in ["phd", "doctor", "research"]):
        return "PhD / Doctoral"
    else:
        return "Other Certificate Programs"

if not df_course.empty:
    df = df_course.copy()
    page_col = "Page path and screen class" if "Page path and screen class" in df.columns else df.columns[0]
    
    # Exclude non-course root paths
    df = df[~df[page_col].isin(["/", "/course", "/course/", "(not set)", ""])].copy()

    # Dynamic Column Mapping
    views_col = next((c for c in ["Views", "Event count", "Screen views"] if c in df.columns), None)
    users_col = next((c for c in ["Active users", "Users", "Total users"] if c in df.columns), None)
    sessions_col = next((c for c in ["Sessions", "Engaged sessions"] if c in df.columns), None)
    events_col = next((c for c in ["Key events", "Conversions"] if c in df.columns), None)
    date_col = next((c for c in ["Date", "Nth day"] if c in df.columns), None)

    df["Views"] = pd.to_numeric(df[views_col], errors='coerce').fillna(0) if views_col else 0
    df["Active Users"] = pd.to_numeric(df[users_col], errors='coerce').fillna(0) if users_col else 0
    df["Sessions"] = pd.to_numeric(df[sessions_col], errors='coerce').fillna(0) if sessions_col else df["Views"]
    df["Conversions"] = pd.to_numeric(df[events_col], errors='coerce').fillna(0) if events_col else 0

    df["Degree Level"] = df[page_col].apply(categorize_program_level)
    df["Course Title"] = df[page_col].apply(clean_course_name)

    # Date Parsing logic
    has_valid_dates = False
    if date_col and date_col in df.columns:
        df["Date_Parsed"] = pd.to_datetime(df[date_col].astype(str), format="%Y%m%d", errors="coerce")
        if df["Date_Parsed"].isna().all():
            df["Date_Parsed"] = pd.to_datetime(df[date_col], errors="coerce")
        if not df["Date_Parsed"].isna().all():
            has_valid_dates = True

    # --- 1. EXECUTIVE METRICS HEADER ---
    tot_views = df["Views"].sum()
    tot_users = df["Active Users"].sum()
    tot_sessions = df["Sessions"].sum()
    tot_leads = df["Conversions"].sum()
    tot_programs = df["Course Title"].nunique()
    lead_yield = (tot_leads / tot_users * 100) if tot_users > 0 else 0

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Programs Monitored", f"{tot_programs:,}")
    m2.metric("Course Views", f"{int(tot_views):,}")
    m3.metric("Total Sessions", f"{int(tot_sessions):,}")
    m4.metric("Active Applicants", f"{int(tot_users):,}")
    m5.metric("Lead Conversions", f"{int(tot_leads):,}")
    m6.metric("Lead Yield Rate", f"{lead_yield:.2f}%")

    st.markdown("---")

    # --- CHART 1: DAILY COURSE DEMAND TREND ---
    st.subheader("📈 Daily Course Demand Trend")
    
    if has_valid_dates:
        daily_course = df.groupby(["Date_Parsed", "Degree Level"])[["Views", "Sessions", "Active Users"]].sum().reset_index()
        fig_trend = px.line(
            daily_course, 
            x="Date_Parsed", 
            y="Views", 
            color="Degree Level",
            labels={"Views": "Daily Views", "Date_Parsed": "Date", "Degree Level": "Program Level"},
            color_discrete_sequence=px.colors.qualitative.Set1
        )
        fig_trend.update_layout(height=380, margin=dict(l=20, r=20, t=20, b=20), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_trend, width="stretch")
    else:
        st.info("💡 Add a `Date` column (formatted as `YYYYMMDD` or `YYYY-MM-DD`) to `02_Course_GA4.csv` to enable date-wise trend lines.")
        
        # Static Fallback Chart when Date is missing
        level_views = df.groupby("Degree Level")[["Views", "Sessions", "Active Users"]].sum().reset_index()
        fig_bar_level = px.bar(
            level_views, 
            x="Degree Level", 
            y=["Views", "Sessions"], 
            barmode="group",
            labels={"value": "Volume", "variable": "Metric"}
        )
        fig_bar_level.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_bar_level, width="stretch")

    st.markdown("---")

    # --- CHART 2 & CHART 3: DEGREE SHARE & TOP 10 DEMAND ---
    col1, col2 = st.columns([4, 6])

    with col1:
        st.subheader("🍩 Demand Share by Degree Level")
        deg_summary = df.groupby("Degree Level")["Views"].sum().reset_index()
        fig_deg = px.pie(
            deg_summary, 
            values="Views", 
            names="Degree Level", 
            hole=0.45, 
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_deg.update_traces(textposition='inside', textinfo='percent+label')
        fig_deg.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10), showlegend=False)
        st.plotly_chart(fig_deg, width="stretch")

    with col2:
        st.subheader("🏆 Top 10 Most Demanded Academic Programs")
        course_agg = df.groupby(["Course Title", "Degree Level"]).agg({
            "Views": "sum",
            "Active Users": "sum",
            "Conversions": "sum"
        }).reset_index()

        top10_courses = course_agg.sort_values(by="Views", ascending=True).tail(10)
        fig_top_courses = px.bar(
            top10_courses, 
            x="Views", 
            y="Course Title", 
            orientation="h", 
            color="Degree Level",
            text_auto=",.0f"
        )
        fig_top_courses.update_layout(height=380, yaxis_title="", margin=dict(l=150, r=20, t=20, b=10))
        st.plotly_chart(fig_top_courses, width="stretch")

    st.markdown("---")

    # --- CHART 4 & CHART 5: HIERARCHY TREEMAP & DEVICE ATTRIBUTION ---
    col3, col4 = st.columns([6, 4])

    with col3:
        st.subheader("🗺️ Course Demand & Conversion Hierarchy")
        st.caption("Tile size = Student Demand (Views) | Color Intensity = Lead Conversions")

        fig_tree = px.treemap(
            course_agg,
            path=[px.Constant("All Course Offerings"), "Degree Level", "Course Title"],
            values="Views",
            color="Conversions",
            color_continuous_scale="Tealgrn",
            hover_data=["Active Users"]
        )
        fig_tree.update_layout(height=400, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig_tree, width="stretch")

    with col4:
        st.subheader("📱 Course Visitor Share by Device")
        if not df_device.empty:
            dev_col = "Device category" if "Device category" in df_device.columns else df_device.columns[0]
            val_col = "Active users" if "Active users" in df_device.columns else df_device.columns[1]
            
            fig_dev = px.pie(
                df_device, 
                values=val_col, 
                names=dev_col, 
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_dev.update_traces(textposition='inside', textinfo='percent+label')
            fig_dev.update_layout(height=400, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig_dev, width="stretch")
        else:
            st.info("💡 Upload `04_Device_GA4.csv` to display Mobile vs. Desktop visitor splits.")

    st.markdown("---")

    # --- CHART 6: WHAT COURSES ARE USERS SEARCHING FOR? ---
    st.subheader("🔎 What Course Keywords Are Users Searching on Google? (GSC Data)")
    if not df_gsc.empty:
        q_col = "Query" if "Query" in df_gsc.columns else df_gsc.columns[0]
        imp_col = "Impressions" if "Impressions" in df_gsc.columns else "Impressions"
        click_col = "Clicks" if "Clicks" in df_gsc.columns else "Clicks"

        # Filter queries related to academic courses and admissions
        course_keywords = df_gsc[df_gsc[q_col].astype(str).str.contains("course|btech|msc|bsc|mba|bba|phd|diploma|admission|fees|syllabus", case=False, na=False)]
        
        display_q = course_keywords if not course_keywords.empty else df_gsc
        top_queries = display_q.sort_values(by=imp_col, ascending=True).tail(12)

        fig_gsc = px.bar(
            top_queries,
            x=imp_col,
            y=q_col,
            orientation="h",
            color=click_col,
            labels={imp_col: "Google Search Impressions", q_col: "Search Query", click_col: "Organic Clicks"},
            color_continuous_scale="Cividis",
            text_auto=",.0f"
        )
        fig_gsc.update_layout(height=400, margin=dict(l=180, r=20, t=20, b=20))
        st.plotly_chart(fig_gsc, width="stretch")
    else:
        st.info("💡 Upload `gsc_queries.csv` into `data/input/` to view prospective student search terms.")

    st.markdown("---")

    # --- AUDIT TABLE FOR ALL 42-100 COURSES ---
    st.subheader("📊 Individual Course Directory & Performance Table (~42–100 Courses)")
    
    selected_deg = st.multiselect(
        "Filter Programs by Degree Level:", 
        options=list(course_agg["Degree Level"].unique()), 
        default=list(course_agg["Degree Level"].unique())
    )
    
    filtered_courses = course_agg[course_agg["Degree Level"].isin(selected_deg)].sort_values(by="Views", ascending=False)
    st.dataframe(filtered_courses, width="stretch", height=400)

else:
    st.info("💡 Upload `02_Course_GA4.csv` into `data/input/` to populate course intelligence.")