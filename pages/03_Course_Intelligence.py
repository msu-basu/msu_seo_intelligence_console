"""
03_Course_Intelligence.py
-------------------------
Academic Course Intelligence & Demand Analytics featuring:
- Tab 1: Core Intelligence & Hierarchy (Degree share, Top 10, Treemap, Device, Geo, GSC queries, Directory)
- Tab 2: Day-Wise & Month-Wise Demand Trends (Interactive date range, 7-day rolling average, multi-course comparison, MoM growth)
- Tab 3: Top Performing Programs Leaderboard (Standout Champion, Volume leaders, Degree level winners, Peak surge leaders)
- Tab 4: Demand Spikes & Outlier Registry (Statistical anomaly detection, timeline scatter, single-course drilldown, incident log)
Optimized with Streamlit in-memory caching (@st.cache_data) for instantaneous sub-second chart rendering.
"""

import re
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from src.data.loaders import detect_and_load_all
from src.data.normalizers import (
    categorize_program_level,
    clean_course_name,
    find_course_page_column,
    is_course_path,
    normalize_percent_series,
    parse_numeric_series,
)
from src.analytics.course_spikes import (
    prepare_clean_daily_course_df,
    get_day_wise_course_performance,
    get_month_wise_course_performance,
    get_top_performing_courses,
    detect_course_outliers,
)

# =============================================================================
# PAGE STYLES
# =============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

div[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}
div[data-testid="metric-container"] label {
    color: #94a3b8 !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #f1f5f9 !important;
    font-size: 26px !important;
    font-weight: 700 !important;
}
.section-header {
    font-size: 18px; font-weight: 600; color: #38bdf8;
    border-left: 4px solid #38bdf8; padding-left: 10px;
    margin: 20px 0 12px 0;
}
</style>
""", unsafe_allow_html=True)

st.title("🎓 Academic Course Intelligence & Demand Analytics")
st.caption(
    "Granular tracking across individual course URLs, degree level categorizations, "
    "daily time-series trends, device attribution, location intelligence, and Google search queries."
)

# =============================================================================
# DATA INITIALIZATION
# =============================================================================
datasets = detect_and_load_all()
df_course = datasets.get("course", pd.DataFrame())
df_gsc = datasets.get("course_gsc_queries", datasets.get("gsc_queries", pd.DataFrame()))
df_device = datasets.get("device", pd.DataFrame())
df_geo = datasets.get("geo", pd.DataFrame())
df_countries = datasets.get("countries", pd.DataFrame())

if df_course.empty:
    st.error("No course dataset detected in `data/processed/`. Expected `02_Course_GA4.parquet`.")
    st.stop()

df = df_course.copy()

# Robust page-column detection
page_col = find_course_page_column(
    df,
    preferred=["Page path and screen class", "Page path", "URL", "Top pages"],
)

# Keep only genuine course page paths
df = df[df[page_col].apply(is_course_path)].copy()
if df.empty:
    st.warning("No genuine `/course/...` or `/courses/...` paths were found.")
    st.stop()

# Derived course dimensions
df["Course Title"] = df[page_col].apply(clean_course_name)
df["Degree Level"] = df[page_col].apply(categorize_program_level)
df["Course Title"] = df["Course Title"].fillna("Unknown Program").astype(str).replace({"": "Unknown Program", "nan": "Unknown Program"})
df["Degree Level"] = df["Degree Level"].fillna("Other Certificate Programs").astype(str).replace({"": "Other Certificate Programs", "nan": "Other Certificate Programs"})

# Metric Column Mapping
def first_column(exact_names=(), keyword_groups=()):
    lowered = {str(c).strip().lower(): c for c in df.columns}
    for name in exact_names:
        found = lowered.get(name.lower())
        if found is not None:
            return found
    for keywords in keyword_groups:
        for column in df.columns:
            name = str(column).strip().lower()
            if all(keyword in name for keyword in keywords):
                return column
    return None

views_col = first_column(exact_names=["Views", "Screen views", "Impressions"], keyword_groups=[("views",)])
users_col = first_column(exact_names=["Active users", "Total users", "Users"], keyword_groups=[("active", "users"), ("users",)])
sessions_col = first_column(exact_names=["Sessions", "Engaged sessions"], keyword_groups=[("sessions",)])
clicks_col = first_column(exact_names=["Clicks", "Organic Clicks"], keyword_groups=[("click",)])
events_col = first_column(exact_names=["Key events", "Conversions", "Event count", "Leads"], keyword_groups=[("key", "events"), ("event", "count"), ("conversion",), ("lead",)])
rate_col = first_column(exact_names=["CTR", "Engagement rate"], keyword_groups=[("engagement", "rate"), ("ctr",)])
date_col = first_column(exact_names=["Date"], keyword_groups=[("date",), ("nth", "day")])

df["Views"] = parse_numeric_series(df[views_col], df.index).round(0).astype("int64") if views_col else pd.Series(0, index=df.index, dtype="int64")
df["Active Users"] = parse_numeric_series(df[users_col], df.index).round(0).astype("int64") if users_col else pd.Series(0, index=df.index, dtype="int64")
df["Sessions"] = parse_numeric_series(df[sessions_col], df.index).round(0).astype("int64") if sessions_col else pd.Series(0, index=df.index, dtype="int64")
df["Clicks"] = parse_numeric_series(df[clicks_col], df.index).round(0).astype("int64") if clicks_col else pd.Series(0, index=df.index, dtype="int64")
df["Conversions"] = parse_numeric_series(df[events_col], df.index).round(0).astype("int64") if events_col else pd.Series(0, index=df.index, dtype="int64")

if rate_col:
    df["CTR"] = normalize_percent_series(parse_numeric_series(df[rate_col], df.index))
else:
    df["CTR"] = pd.Series(0.0, index=df.index, dtype="float64")

# Date Parsing
has_valid_dates = False
if date_col and date_col in df.columns:
    df["Date_Parsed"] = pd.to_datetime(df[date_col].astype(str), format="%Y%m%d", errors="coerce")
    if df["Date_Parsed"].isna().all():
        df["Date_Parsed"] = pd.to_datetime(df[date_col], errors="coerce")
    if not df["Date_Parsed"].isna().all():
        has_valid_dates = True

# Prepared daily dataframe for time series & spikes (Cached in RAM)
df_course_daily_clean = prepare_clean_daily_course_df(df_course)

# =============================================================================
# TOP-LEVEL NAVIGATION TABS (UNCLUTTERED ARCHITECTURE)
# =============================================================================
tab_overview, tab_trends, tab_leaderboard, tab_outliers = st.tabs([
    "📊 Core Intelligence & Hierarchy",
    "📈 Day-Wise & Month-Wise Demand Trends",
    "🏆 Top Performing Programs",
    "🚨 Demand Spikes & Outlier Registry"
])

# =============================================================================
# TAB 1: CORE INTELLIGENCE & CONVERSION HIERARCHY
# =============================================================================
with tab_overview:
    # 1. EXECUTIVE METRICS HEADER
    tot_views = df["Views"].sum()
    tot_users = df["Active Users"].sum()
    tot_sessions = df["Sessions"].sum()
    tot_clicks = df["Clicks"].sum()
    tot_leads = df["Conversions"].sum()
    tot_programs = df["Course Title"].nunique()

    tot_traffic = tot_sessions if tot_sessions > 0 else (tot_clicks if tot_clicks > 0 else tot_views)
    lead_yield = (tot_leads / tot_traffic * 100) if tot_traffic > 0 else 0.0

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Programs Monitored", f"{tot_programs:,}")
    m2.metric("Total Clicks", f"{int(tot_clicks):,}" if tot_clicks > 0 else f"{int(tot_views):,}")
    m3.metric("Total Sessions", f"{int(tot_sessions):,}")
    m4.metric("Active Applicants", f"{int(tot_users):,}")
    m5.metric("Lead Conversions", f"{int(tot_leads):,}")
    m6.metric("Lead Conv. Rate", f"{lead_yield:.2f}%")

    st.markdown("---")

    # 2. STRATEGIC HIGHLIGHTS
    df_traffic_col = "Sessions" if tot_sessions > 0 else ("Clicks" if tot_clicks > 0 else "Views")
    if not df.empty and df[df_traffic_col].sum() > 0:
        top_traffic = df.loc[df[df_traffic_col].idxmax()]
        top_ctr_idx = df["CTR"].idxmax()
        top_ctr_course = df.loc[top_ctr_idx] if df["CTR"].max() > 0 else top_traffic

        med_sess = df[df_traffic_col].median()
        opp_candidates = df[df[df_traffic_col] >= med_sess]
        opp_course = (
            opp_candidates.loc[opp_candidates["CTR"].idxmin()]
            if not opp_candidates.empty and opp_candidates["CTR"].min() >= 0
            else df.iloc[0]
        )

        st.subheader("💡 Strategic Insights & Highlights")
        hc1, hc2, hc3 = st.columns(3)
        with hc1:
            st.info(
                f"🌟 **Top Demand Driver**\n\n**{top_traffic['Course Title']}**\n\n"
                f"• {df_traffic_col}: **{int(top_traffic[df_traffic_col]):,}** | Clicks/Views: **{int(top_traffic['Views']):,}**"
            )
        with hc2:
            st.success(
                f"🎯 **Highest Engagement / CTR**\n\n**{top_ctr_course['Course Title']}**\n\n"
                f"• Engagement Rate: **{top_ctr_course['CTR']:.2f}%** | Leads: **{int(top_ctr_course['Conversions']):,}**"
            )
        with hc3:
            st.warning(
                f"⚠️ **CRO Priority Program**\n\n**{opp_course['Course Title']}**\n\n"
                f"High traffic (**{int(opp_course[df_traffic_col]):,}** visits) with room for UX/CTA conversion optimization."
            )
        st.markdown("---")

    # 3. DEGREE SHARE & TOP 10 DEMAND
    col1, col2 = st.columns([4, 6])
    with col1:
        st.subheader("📊 Demand Share by Degree Level")
        deg_summary = df.groupby("Degree Level")["Views"].sum().reset_index()
        fig_deg = px.pie(
            deg_summary, values="Views", names="Degree Level", hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_deg.update_traces(textposition="inside", textinfo="percent+label")
        fig_deg.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10), showlegend=False)
        st.plotly_chart(fig_deg, use_container_width=True)

    with col2:
        st.subheader("🏅 Top 10 Most Demanded Academic Programs")
        course_agg = (
            df.groupby(["Course Title", "Degree Level"], dropna=False)
            .agg({
                "Views": "sum", "Sessions": "sum", "Active Users": "sum",
                "Clicks": "sum", "Conversions": "sum", "CTR": "mean"
            })
            .reset_index()
        )
        for metric in ["Views", "Sessions", "Active Users", "Clicks", "Conversions"]:
            course_agg[metric] = pd.to_numeric(course_agg[metric], errors="coerce").fillna(0).round(0).astype("int64")
        course_agg["CTR"] = pd.to_numeric(course_agg["CTR"], errors="coerce").fillna(0).round(2)

        course_traffic = np.where(
            course_agg["Sessions"] > 0, course_agg["Sessions"],
            np.where(course_agg["Clicks"] > 0, course_agg["Clicks"], course_agg["Views"])
        )
        course_agg["Lead Conv Rate (%)"] = np.where(
            course_traffic > 0, (course_agg["Conversions"] / course_traffic) * 100, 0.0
        ).round(2)

        top10_courses = course_agg.sort_values(by="Views", ascending=True).tail(10)
        fig_top_courses = px.bar(
            top10_courses, x="Views", y="Course Title", orientation="h",
            color="Degree Level", text_auto=",.0f"
        )
        fig_top_courses.update_layout(height=380, yaxis_title="", margin=dict(l=150, r=20, t=20, b=10))
        st.plotly_chart(fig_top_courses, use_container_width=True)

    st.markdown("---")

    # 4. HIERARCHY TREEMAP & DEVICE ATTRIBUTION
    col3, col4 = st.columns([6, 4])
    with col3:
        st.subheader("🗺️ Course Demand & Conversion Hierarchy")
        st.caption("Tile size = Student Demand (Views) | Color Intensity = Lead Conversions")
        fig_tree = px.treemap(
            course_agg,
            path=[px.Constant("All Course Offerings"), "Degree Level", "Course Title"],
            values="Views", color="Conversions",
            color_continuous_scale="Tealgrn", hover_data=["Active Users"]
        )
        fig_tree.update_layout(height=400, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig_tree, use_container_width=True)

    with col4:
        st.subheader("📱 Course Visitor Share by Device")
        if not df_device.empty:
            dev_col = "Device category" if "Device category" in df_device.columns else df_device.columns[0]
            val_col = "Active users" if "Active users" in df_device.columns else df_device.columns[1]
            fig_dev = px.pie(
                df_device, values=val_col, names=dev_col, hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_dev.update_traces(textposition="inside", textinfo="percent+label")
            fig_dev.update_layout(height=400, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig_dev, use_container_width=True)
        else:
            st.info("Upload `04_Device_GA4.parquet` to display Mobile vs. Desktop visitor splits.")

    st.markdown("---")

    # 5. GEOGRAPHIC LOCATION & GSC SEARCH QUERY PERFORMANCE
    col5, col6 = st.columns(2)
    with col5:
        st.subheader("📍 India City Search Intelligence")
        if not df_geo.empty:
            country_col = next((c for c in df_geo.columns if "country" in str(c).lower()), df_geo.columns[0])
            city_col = next((c for c in df_geo.columns if "city" in str(c).lower()), None)
            users_geo_col = next((c for c in df_geo.columns if any(k in str(c).lower() for k in ["users", "active", "sessions", "clicks"])), df_geo.columns[-1])
            df_india = df_geo[df_geo[country_col].astype(str).str.strip().str.lower() == "india"].copy()
            if city_col and not df_india.empty:
                top_cities = (
                    df_india[~df_india[city_col].astype(str).str.lower().isin(["(not set)", "unknown", "nan"])]
                    .groupby(city_col)[users_geo_col].sum().reset_index()
                    .sort_values(by=users_geo_col, ascending=False).head(10)
                )
                fig_city = px.bar(
                    top_cities, x=users_geo_col, y=city_col, orientation="h",
                    title="Top 10 Indian Cities by Applicant Traffic",
                    color=users_geo_col, color_continuous_scale="Purples"
                )
                fig_city.update_layout(yaxis=dict(autorange="reversed"), height=350, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_city, use_container_width=True)
            else:
                st.info("City-level breakdown for India is not available.")
        else:
            st.info("Upload `06_Geo_Global_GA4.parquet` to display city search intelligence.")

    with col6:
        st.subheader("🔍 Top Course Search Queries (Google GSC)")
        if not df_gsc.empty:
            q_col = "Query" if "Query" in df_gsc.columns else df_gsc.columns[0]
            imp_col = "Impressions" if "Impressions" in df_gsc.columns else df_gsc.columns[1]
            click_col = "Clicks" if "Clicks" in df_gsc.columns else df_gsc.columns[2]
            top_queries = df_gsc.sort_values(by=imp_col, ascending=False).head(10)
            fig_gsc = px.bar(
                top_queries, x=imp_col, y=q_col, orientation="h",
                color=click_col, color_continuous_scale="Cividis",
                title="Top Organic Course Keywords by Search Impressions"
            )
            fig_gsc.update_layout(yaxis=dict(autorange="reversed"), height=350, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_gsc, use_container_width=True)
        else:
            st.info("Upload `gsc_course_queries.parquet` to view Google Search terms.")

    st.markdown("---")

    # 6. COURSE DIRECTORY & LEAD CONVERSIONS
    st.subheader("📋 Individual Course Directory & Performance Table")
    tf_col1, tf_col2 = st.columns([2, 1])
    with tf_col1:
        selected_deg = st.multiselect(
            "Filter Programs by Degree Level:",
            options=list(course_agg["Degree Level"].unique()),
            default=list(course_agg["Degree Level"].unique()),
            key="overview_course_deg_filter"
        )
    with tf_col2:
        search_kw = st.text_input("Search Program Title:", placeholder="e.g. Anesthesia, Radiology, BTech...", key="overview_course_search")

    filtered_courses = course_agg[course_agg["Degree Level"].isin(selected_deg)].copy()
    if search_kw.strip():
        filtered_courses = filtered_courses[filtered_courses["Course Title"].str.lower().str.contains(search_kw.lower().strip())]

    filtered_courses = filtered_courses.sort_values(by="Sessions", ascending=False)
    st.dataframe(
        filtered_courses[["Course Title", "Degree Level", "Sessions", "Clicks", "CTR", "Conversions", "Lead Conv Rate (%)"]],
        use_container_width=True, height=350,
        column_config={
            "Sessions": st.column_config.NumberColumn(format="%d"),
            "Clicks": st.column_config.NumberColumn(format="%d"),
            "CTR": st.column_config.NumberColumn("CTR (%)", format="%.2f%%"),
            "Conversions": st.column_config.NumberColumn("Form Leads", format="%d"),
            "Lead Conv Rate (%)": st.column_config.NumberColumn("Lead Conv. Rate", format="%.2f%%"),
        }
    )


# =============================================================================
# TAB 2: DAY-WISE & MONTH-WISE DEMAND TRENDS (INSTANT CACHED RENDERING)
# =============================================================================
with tab_trends:
    st.markdown("<div class='section-header'>📈 Day-Wise & Month-Wise Course Demand Trends</div>", unsafe_allow_html=True)
    st.caption("Granular daily applicant interest curves, date range filtering, monthly demand volume, and MoM growth acceleration.")

    if df_course_daily_clean.empty:
        st.info("Daily grain course data is not available.")
    else:
        min_date = df_course_daily_clean["Date"].min().date()
        max_date = df_course_daily_clean["Date"].max().date()

        sub_tab_c_daily, sub_tab_c_monthly = st.tabs([
            "📅 Day-Wise Demand (Custom Range)",
            "📆 Month-Wise Volume & MoM Growth"
        ])

        with sub_tab_c_daily:
            cd_col1, cd_col2 = st.columns([1, 2])
            with cd_col1:
                c_date_range = st.date_input(
                    "Date Range Filter:",
                    value=[min_date, max_date],
                    min_value=min_date,
                    max_value=max_date,
                    key="course_trends_date_range"
                )
            
            start_cd = c_date_range[0] if isinstance(c_date_range, (list, tuple)) and len(c_date_range) > 0 else min_date
            end_cd = c_date_range[1] if isinstance(c_date_range, (list, tuple)) and len(c_date_range) > 1 else max_date

            all_course_titles = sorted(df_course_daily_clean["Course Title"].unique().tolist())
            with cd_col2:
                chosen_courses = st.multiselect(
                    "Compare Specific Academic Programs (leave empty for Top 5):",
                    options=all_course_titles,
                    default=[],
                    key="course_trends_chosen_courses",
                    help="Overlay specific academic programs on the daily chart"
                )

            total_c_daily_df, per_c_daily_df = get_day_wise_course_performance(
                df_course_daily_clean,
                start_date=start_cd,
                end_date=end_cd,
                selected_courses_tuple=tuple(chosen_courses) if chosen_courses else ()
            )

            if not total_c_daily_df.empty:
                tot_c_range_views = int(total_c_daily_df["Views"].sum())
                avg_c_daily_v = round(total_c_daily_df["Views"].mean(), 1)
                peak_c_row = total_c_daily_df.loc[total_c_daily_df["Views"].idxmax()]
                peak_c_date_str = peak_c_row["Date"].strftime("%d %b %Y")
                peak_c_views_val = int(peak_c_row["Views"])

                cm_1, cm_2, cm_3, cm_4 = st.columns(4)
                cm_1.metric("Course Views in Range", f"{tot_c_range_views:,}")
                cm_2.metric("Avg Daily Demand", f"{avg_c_daily_v:,}")
                cm_3.metric("Peak Daily Views", f"{peak_c_views_val:,}", f"on {peak_c_date_str}")
                cm_4.metric("Days Monitored", f"{len(total_c_daily_df):,}")

                fig_tot_c_daily = px.line(
                    total_c_daily_df,
                    x="Date",
                    y=["Views", "Rolling_7d_Views"],
                    labels={"value": "Views", "Date": "Date", "variable": "Metric"},
                    title="Platform-Wide Daily Course Demand (with 7-Day Rolling Moving Average)",
                    color_discrete_map={"Views": "#a78bfa", "Rolling_7d_Views": "#f59e0b"},
                    template="plotly_dark"
                )
                fig_tot_c_daily.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                    font_color="#f1f5f9", height=350, hovermode="x unified",
                    legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=40, b=10)
                )
                st.plotly_chart(fig_tot_c_daily, use_container_width=True)

                if not per_c_daily_df.empty:
                    st.markdown("#### 🔍 Program-Level Daily Demand Trajectory Comparison")
                    fig_per_c_daily = px.line(
                        per_c_daily_df,
                        x="Date", y="Views", color="Course Title",
                        title="Daily Applicant Demand Trajectory by Program",
                        template="plotly_dark"
                    )
                    fig_per_c_daily.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                        font_color="#f1f5f9", height=360, hovermode="x unified",
                        legend=dict(orientation="h", y=-0.3), margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_per_c_daily, use_container_width=True)

        with sub_tab_c_monthly:
            monthly_c_df = get_month_wise_course_performance(df_course_daily_clean)
            if not monthly_c_df.empty:
                c_mo_1, c_mo_2 = st.columns([3, 2])
                with c_mo_1:
                    fig_c_monthly = px.bar(
                        monthly_c_df,
                        x="YearMonth", y="Views", text="Views",
                        title="Month-Wise Total Academic Course Demand (Views)",
                        color="Views", color_continuous_scale="Purples",
                        template="plotly_dark"
                    )
                    fig_c_monthly.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
                    fig_c_monthly.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                        font_color="#f1f5f9", height=350, coloraxis_showscale=False,
                        margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_c_monthly, use_container_width=True)

                with c_mo_2:
                    fig_c_mom = px.line(
                        monthly_c_df.dropna(subset=["MoM_Growth_%"]),
                        x="YearMonth", y="MoM_Growth_%", markers=True,
                        title="Month-over-Month (MoM) Demand Growth (%)",
                        color_discrete_sequence=["#a855f7"], template="plotly_dark"
                    )
                    fig_c_mom.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
                    fig_c_mom.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                        font_color="#f1f5f9", height=350, margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_c_mom, use_container_width=True)

                st.markdown("#### 📋 Monthly Course Demand Breakdown")
                disp_c_monthly = monthly_c_df.rename(columns={
                    "YearMonth": "Month",
                    "Views": "Total Demand Views",
                    "Active_Users": "Peak Active Applicants",
                    "Courses_Active": "Active Programs",
                    "Avg_Daily_Views": "Daily Avg Views",
                    "MoM_Growth_%": "MoM Growth (%)"
                })
                st.dataframe(
                    disp_c_monthly.style.format({
                        "Total Demand Views": "{:,.0f}",
                        "Peak Active Applicants": "{:,.0f}",
                        "Active Programs": "{:,.0f}",
                        "Daily Avg Views": "{:,.1f}",
                        "MoM Growth (%)": "{:+.1f}%"
                    }),
                    use_container_width=True, hide_index=True
                )


# =============================================================================
# TAB 3: TOP PERFORMING PROGRAMS LEADERBOARD
# =============================================================================
with tab_leaderboard:
    st.markdown("<div class='section-header'>🏆 Top Performing Academic Programs</div>", unsafe_allow_html=True)
    st.caption("Identifies standout academic courses across all-time demand volume, degree level champions, and single-day surge impact.")

    top_c_perf = get_top_performing_courses(df_course_daily_clean, top_n=10)
    c_vol_leaders = top_c_perf.get("volume_leaders", pd.DataFrame())
    c_deg_leaders = top_c_perf.get("degree_leaders", pd.DataFrame())
    c_surge_leaders = top_c_perf.get("surge_leaders", pd.DataFrame())

    if not c_vol_leaders.empty:
        champ_c = c_vol_leaders.iloc[0]
        st.info(
            f"👑 **Most Demanded Academic Program:** **{champ_c['Course Title']}** with "
            f"**{int(champ_c['Views']):,}** total views (avg **{champ_c['Avg_Daily_Views']}** views/day) "
            f"in degree tier *{champ_c['Degree Level']}*!"
        )

        c_lead_tab1, c_lead_tab2, c_lead_tab3 = st.tabs([
            "📊 All-Time Volume Leaders",
            "🥇 Best by Degree Level",
            "⚡ Peak Single-Day Surge Leaders"
        ])

        with c_lead_tab1:
            fig_c_top_bar = px.bar(
                c_vol_leaders, x="Views", y="Course Title", orientation="h",
                color="Degree Level", title=f"Top {len(c_vol_leaders)} Programs by Demand Volume",
                template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_c_top_bar.update_layout(
                yaxis=dict(autorange="reversed"), paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#0f172a", font_color="#f1f5f9", height=360,
                legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_c_top_bar, use_container_width=True)

            st.dataframe(
                c_vol_leaders[["Course Title", "Degree Level", "Views", "Est_Sessions", "Avg_Daily_Views", "Peak_Single_Day_Views"]].rename(columns={
                    "Views": "Total Demand Views",
                    "Est_Sessions": "Est. Sessions",
                    "Avg_Daily_Views": "Daily Avg",
                    "Peak_Single_Day_Views": "Peak Day"
                }),
                use_container_width=True, hide_index=True
            )

        with c_lead_tab2:
            st.markdown("#### 🏅 Standout Program for Each Degree Level")
            st.dataframe(
                c_deg_leaders[["Degree Level", "Course Title", "Views", "Est_Sessions", "Avg_Daily_Views"]].rename(columns={
                    "Views": "Top Level Views",
                    "Est_Sessions": "Est. Sessions",
                    "Avg_Daily_Views": "Daily Avg"
                }),
                use_container_width=True, hide_index=True
            )

        with c_lead_tab3:
            st.markdown("#### ⚡ Academic Programs with Highest Single-Day Applicant Surges")
            st.dataframe(
                c_surge_leaders[["Course Title", "Degree Level", "Peak_Single_Day_Views", "Views", "Avg_Daily_Views"]].rename(columns={
                    "Peak_Single_Day_Views": "Peak Single-Day Views",
                    "Views": "Total Demand Views",
                    "Avg_Daily_Views": "Normal Daily Avg"
                }),
                use_container_width=True, hide_index=True
            )


# =============================================================================
# TAB 4: DEMAND SPIKES & OUTLIER REGISTRY
# =============================================================================
with tab_outliers:
    st.markdown("<div class='section-header'>🚨 Academic Demand Spikes & Outlier Registry</div>", unsafe_allow_html=True)
    st.caption(
        "Automated statistical anomaly detection (Z-score ≥ 2.5 or Surge Ratio ≥ 2.2x normal baseline). "
        "Records admissions announcement spikes, exam result interest surges, and breaking program demand."
    )

    c_outliers_df = detect_course_outliers(df_course_daily_clean, min_views=15, z_threshold=2.5, ratio_threshold=2.2)

    if not c_outliers_df.empty:
        c_tot_outliers = len(c_outliers_df)
        c_max_surge = c_outliers_df.sort_values("Spike_Views", ascending=False).iloc[0]
        c_max_mult = c_outliers_df.sort_values("Surge_Multiplier", ascending=False).iloc[0]

        cok1, cok2, cok3, cok4 = st.columns(4)
        cok1.metric("Demand Spikes Detected", f"{c_tot_outliers}")
        cok2.metric("Highest Single-Day Demand", f"{int(c_max_surge['Spike_Views'])} Views", f"on {c_max_surge['Date'].strftime('%d %b %Y')}")
        cok3.metric("Largest Surge Factor", f"{c_max_mult['Surge_Multiplier']}", f"{c_max_mult['Course Title'][:18]}...")
        cok4.metric("Algorithm", "Z-Score ≥ 2.5", "Rolling Baseline")

        # Scatter Timeline
        fig_c_outlier_time = px.scatter(
            c_outliers_df,
            x="Date", y="Spike_Views", size="Spike_Views", color="Degree Level",
            hover_name="Course Title",
            hover_data={"Date": "|%d %b %Y", "Surge_Multiplier": True, "Baseline_Avg": True, "Spike_Tag": True},
            title="Timeline of Recorded Program Demand Spike Events",
            template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_c_outlier_time.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
            font_color="#f1f5f9", height=360, margin=dict(l=10, r=10, t=40, b=10)
        )
        st.plotly_chart(fig_c_outlier_time, use_container_width=True)

        # Micro-Inspector
        st.markdown("#### 🔬 Inspect Individual Program Demand Trajectory vs Baseline")
        c_spike_titles = sorted(c_outliers_df["Course Title"].unique().tolist())
        c_inspected_title = st.selectbox("Select Academic Program to View Trajectory:", options=c_spike_titles, key="tab_c_outliers_select")

        c_article_daily_df = df_course_daily_clean[df_course_daily_clean["Course Title"] == c_inspected_title].sort_values("Date")
        if not c_article_daily_df.empty:
            fig_c_inspect = px.line(
                c_article_daily_df,
                x="Date", y="Views", markers=True,
                title=f"Daily Demand Trajectory for: {c_inspected_title}",
                template="plotly_dark", color_discrete_sequence=["#a855f7"]
            )
            c_avg_val = c_article_daily_df["Views"].mean()
            fig_c_inspect.add_hline(
                y=c_avg_val, line_dash="dot", line_color="#f59e0b",
                annotation_text=f"Baseline Avg: {c_avg_val:.1f} views/day",
                annotation_position="bottom right"
            )
            fig_c_inspect.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                font_color="#f1f5f9", height=320, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_c_inspect, use_container_width=True)

        # Incident Registry Table & CSV Export
        st.markdown("#### 📋 Recorded Course Demand Spikes Incident Registry")
        disp_c_outliers = c_outliers_df.rename(columns={
            "Course Title": "Academic Program",
            "Spike_Views": "Spike Demand Views",
            "Baseline_Avg": "Baseline Avg",
            "Surge_Multiplier": "Surge Factor",
            "Z_Score": "Z-Score",
            "Spike_Tag": "Surge Tag"
        })
        st.dataframe(
            disp_c_outliers[["Date", "Academic Program", "Degree Level", "Spike Demand Views", "Baseline Avg", "Surge Factor", "Surge Tag"]],
            use_container_width=True, hide_index=True
        )

        st.download_button(
            label="📥 Export Course Demand Spikes Log (CSV)",
            data=c_outliers_df.to_csv(index=False).encode("utf-8"),
            file_name="course_demand_spikes_log.csv",
            mime="text/csv",
            key="tab_c_outliers_download_csv"
        )
    else:
        st.success("No statistical demand outliers detected under current thresholds.")