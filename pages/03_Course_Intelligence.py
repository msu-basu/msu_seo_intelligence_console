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

st.set_page_config(page_title="Course Intelligence", layout="wide")
st.title("🎓 Academic Course Intelligence & Demand Analytics")
st.caption(
    "Granular tracking across ~42–100 individual course URLs, degree level categorizations, "
    "daily time-series trends, device attribution, location intelligence, and Google search queries."
)

datasets = detect_and_load_all()
df_course = datasets.get("course", pd.DataFrame())
df_gsc = datasets.get("course_gsc_queries", datasets.get("gsc_queries", pd.DataFrame()))
df_device = datasets.get("device", pd.DataFrame())
df_geo = datasets.get("geo", pd.DataFrame())
df_countries = datasets.get("countries", pd.DataFrame())

if not df_course.empty:
    df = df_course.copy()

    # Robust page-column detection. Prefer the actual GA4 course export field.
    page_col = find_course_page_column(
        df,
        preferred=["Page path and screen class", "Page path", "URL", "Top pages"],
    )

    # Keep only genuine course page paths; GA4 can include unrelated blog/assets rows.
    df = df[df[page_col].apply(is_course_path)].copy()

    if df.empty:
        st.warning(
            "No genuine `/course/...` or `/courses/...` paths were found in the selected column."
        )
        st.stop()

    # Build the derived course dimensions expected throughout this page.
    df["Course Title"] = df[page_col].apply(clean_course_name)
    df["Degree Level"] = df[page_col].apply(categorize_program_level)

    df["Course Title"] = (
        df["Course Title"]
        .fillna("Unknown Program")
        .astype(str)
        .replace({"": "Unknown Program", "nan": "Unknown Program"})
    )
    df["Degree Level"] = (
        df["Degree Level"]
        .fillna("Other Certificate Programs")
        .astype(str)
        .replace({"": "Other Certificate Programs", "nan": "Other Certificate Programs"})
    )

    # Metric Column Mapping with exact-name priority.
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

    views_col = first_column(
        exact_names=["Views", "Screen views", "Impressions"],
        keyword_groups=[("views",)],
    )
    users_col = first_column(
        exact_names=["Active users", "Total users", "Users"],
        keyword_groups=[("active", "users"), ("users",)],
    )
    sessions_col = first_column(
        exact_names=["Sessions", "Engaged sessions"],
        keyword_groups=[("sessions",)],
    )
    clicks_col = first_column(
        exact_names=["Clicks", "Organic Clicks"],
        keyword_groups=[("click",)],
    )
    events_col = first_column(
        exact_names=["Key events", "Conversions", "Event count", "Leads"],
        keyword_groups=[("key", "events"), ("event", "count"), ("conversion",), ("lead",)],
    )
    rate_col = first_column(
        exact_names=["CTR", "Engagement rate"],
        keyword_groups=[("engagement", "rate"), ("ctr",)],
    )
    date_col = first_column(
        exact_names=["Date"],
        keyword_groups=[("date",), ("nth", "day")],
    )

    df["Views"] = (
        parse_numeric_series(df[views_col], df.index).round(0).astype("int64")
        if views_col
        else pd.Series(0, index=df.index, dtype="int64")
    )
    df["Active Users"] = (
        parse_numeric_series(df[users_col], df.index).round(0).astype("int64")
        if users_col
        else pd.Series(0, index=df.index, dtype="int64")
    )
    df["Sessions"] = (
        parse_numeric_series(df[sessions_col], df.index).round(0).astype("int64")
        if sessions_col
        else pd.Series(0, index=df.index, dtype="int64")
    )
    df["Clicks"] = (
        parse_numeric_series(df[clicks_col], df.index).round(0).astype("int64")
        if clicks_col
        else pd.Series(0, index=df.index, dtype="int64")
    )
    df["Conversions"] = (
        parse_numeric_series(df[events_col], df.index).round(0).astype("int64")
        if events_col
        else pd.Series(0, index=df.index, dtype="int64")
    )

    if rate_col:
        df["CTR"] = normalize_percent_series(
            parse_numeric_series(df[rate_col], df.index)
        )
    else:
        df["CTR"] = pd.Series(0.0, index=df.index, dtype="float64")

    # Date Parsing logic
    has_valid_dates = False
    if date_col and date_col in df.columns:
        df["Date_Parsed"] = pd.to_datetime(
            df[date_col].astype(str), format="%Y%m%d", errors="coerce"
        )
        if df["Date_Parsed"].isna().all():
            df["Date_Parsed"] = pd.to_datetime(df[date_col], errors="coerce")
        if not df["Date_Parsed"].isna().all():
            has_valid_dates = True

    # --- 1. EXECUTIVE METRICS HEADER ---
    tot_views = df["Views"].sum()
    tot_users = df["Active Users"].sum()
    tot_sessions = df["Sessions"].sum()
    tot_clicks = df["Clicks"].sum()
    tot_leads = df["Conversions"].sum()
    tot_programs = df["Course Title"].nunique()

    # Dynamic traffic fallback logic for lead yield rate
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

    # --- 2. STRATEGIC HIGHLIGHTS ---
    df_traffic_col = "Sessions" if tot_sessions > 0 else ("Clicks" if tot_clicks > 0 else "Views")
    if not df.empty and df[df_traffic_col].sum() > 0:
        top_traffic = df.loc[df[df_traffic_col].idxmax()]
        top_ctr_idx = df["CTR"].idxmax()
        top_ctr_course = (
            df.loc[top_ctr_idx] if df["CTR"].max() > 0 else top_traffic
        )

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
                f"🏆 **Top Demand Driver**\n\n**{top_traffic['Course Title']}**\n\n"
                f"• {df_traffic_col}: **{int(top_traffic[df_traffic_col]):,}** | Clicks/Views: **{int(top_traffic['Views']):,}**"
            )
        with hc2:
            st.success(
                f"🔥 **Highest Engagement / CTR**\n\n**{top_ctr_course['Course Title']}**\n\n"
                f"• Engagement Rate: **{top_ctr_course['CTR']:.2f}%** | Leads: **{int(top_ctr_course['Conversions']):,}**"
            )
        with hc3:
            st.warning(
                f"⚡ **CRO Priority Program**\n\n**{opp_course['Course Title']}**\n\n"
                f"High traffic (**{int(opp_course[df_traffic_col]):,}** visits) with room for UX/CTA conversion optimization."
            )

        st.markdown("---")

    # --- CHART 1: DAILY COURSE DEMAND TREND ---
    st.subheader("📈 Daily Course Demand Trend")

    if has_valid_dates:
        daily_course = (
            df.groupby(["Date_Parsed", "Degree Level"])[
                ["Views", "Sessions", "Active Users"]
            ]
            .sum()
            .reset_index()
        )
        fig_trend = px.line(
            daily_course,
            x="Date_Parsed",
            y="Views",
            color="Degree Level",
            labels={
                "Views": "Daily Views",
                "Date_Parsed": "Date",
                "Degree Level": "Program Level",
            },
            color_discrete_sequence=px.colors.qualitative.Set1,
        )
        fig_trend.update_layout(
            height=380,
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_trend, width="stretch")
    else:
        st.info(
            "💡 Add a `Date` column (formatted as `YYYYMMDD` or `YYYY-MM-DD`) to `02_Course_GA4.csv` to enable date-wise trend lines."
        )

        level_views = (
            df.groupby("Degree Level")[["Views", "Sessions", "Active Users"]]
            .sum()
            .reset_index()
        )
        fig_bar_level = px.bar(
            level_views,
            x="Degree Level",
            y=["Views", "Sessions"],
            barmode="group",
            labels={"value": "Volume", "variable": "Metric"},
        )
        fig_bar_level.update_layout(
            height=350, margin=dict(l=20, r=20, t=20, b=20)
        )
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
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig_deg.update_traces(textposition="inside", textinfo="percent+label")
        fig_deg.update_layout(
            height=380, margin=dict(l=10, r=10, t=20, b=10), showlegend=False
        )
        st.plotly_chart(fig_deg, width="stretch")

    with col2:
        st.subheader("🏆 Top 10 Most Demanded Academic Programs")
        course_agg = (
            df.groupby(["Course Title", "Degree Level"], dropna=False)
            .agg(
                {
                    "Views": "sum",
                    "Sessions": "sum",
                    "Active Users": "sum",
                    "Clicks": "sum",
                    "Conversions": "sum",
                    "CTR": "mean",
                }
            )
            .reset_index()
        )

        for metric in ["Views", "Sessions", "Active Users", "Clicks", "Conversions"]:
            course_agg[metric] = (
                pd.to_numeric(course_agg[metric], errors="coerce")
                .fillna(0)
                .round(0)
                .astype("int64")
            )
        course_agg["CTR"] = (
            pd.to_numeric(course_agg["CTR"], errors="coerce").fillna(0).round(2)
        )

        # Dynamic conversion rate formula with traffic fallbacks
        course_traffic = np.where(
            course_agg["Sessions"] > 0,
            course_agg["Sessions"],
            np.where(course_agg["Clicks"] > 0, course_agg["Clicks"], course_agg["Views"])
        )
        course_agg["Lead Conv Rate (%)"] = np.where(
            course_traffic > 0,
            (course_agg["Conversions"] / course_traffic) * 100,
            0.0
        ).round(2)

        top10_courses = course_agg.sort_values(by="Views", ascending=True).tail(10)
        fig_top_courses = px.bar(
            top10_courses,
            x="Views",
            y="Course Title",
            orientation="h",
            color="Degree Level",
            text_auto=",.0f",
        )
        fig_top_courses.update_layout(
            height=380, yaxis_title="", margin=dict(l=150, r=20, t=20, b=10)
        )
        st.plotly_chart(fig_top_courses, width="stretch")

    st.markdown("---")

    # --- CHART 4 & CHART 5: HIERARCHY TREEMAP & DEVICE ATTRIBUTION ---
    col3, col4 = st.columns([6, 4])

    with col3:
        st.subheader("🗺️ Course Demand & Conversion Hierarchy")
        st.caption(
            "Tile size = Student Demand (Views) | Color Intensity = Lead Conversions"
        )

        fig_tree = px.treemap(
            course_agg,
            path=[
                px.Constant("All Course Offerings"),
                "Degree Level",
                "Course Title",
            ],
            values="Views",
            color="Conversions",
            color_continuous_scale="Tealgrn",
            hover_data=["Active Users"],
        )
        fig_tree.update_layout(
            height=400, margin=dict(l=10, r=10, t=20, b=10)
        )
        st.plotly_chart(fig_tree, width="stretch")

    with col4:
        st.subheader("📱 Course Visitor Share by Device")
        if not df_device.empty:
            dev_col = (
                "Device category"
                if "Device category" in df_device.columns
                else df_device.columns[0]
            )
            val_col = (
                "Active users"
                if "Active users" in df_device.columns
                else df_device.columns[1]
            )

            fig_dev = px.pie(
                df_device,
                values=val_col,
                names=dev_col,
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig_dev.update_traces(
                textposition="inside", textinfo="percent+label"
            )
            fig_dev.update_layout(
                height=400, margin=dict(l=10, r=10, t=20, b=10)
            )
            st.plotly_chart(fig_dev, width="stretch")
        else:
            st.info(
                "💡 Upload `04_Device_GA4.csv` to display Mobile vs. Desktop visitor splits."
            )

    st.markdown("---")

    # --- 🌍 GEOGRAPHIC & INDIA CITY SEARCH LOCATION INTELLIGENCE ---
    st.subheader("📍 Geographic & India City Search Intelligence")
    
    geo_data_available = False
    if not df_geo.empty:
        country_col = next((c for c in df_geo.columns if "country" in str(c).lower()), df_geo.columns[0])
        city_col = next((c for c in df_geo.columns if "city" in str(c).lower()), None)
        users_geo_col = next((c for c in df_geo.columns if any(k in str(c).lower() for k in ["users", "active", "sessions", "clicks"])), df_geo.columns[-1])

        df_india = df_geo[df_geo[country_col].astype(str).str.strip().str.lower() == "india"].copy()
        
        if city_col and not df_india.empty:
            df_india = df_india[~df_india[city_col].astype(str).str.lower().isin(["(not set)", "nan", "unknown"])]
            df_india[users_geo_col] = pd.to_numeric(df_india[users_geo_col], errors="coerce").fillna(0)
            
            city_agg = df_india.groupby(city_col)[users_geo_col].sum().reset_index().sort_values(by=users_geo_col, ascending=False)
            
            if not city_agg.empty:
                geo_data_available = True
                top_city = city_agg.iloc[0]
                
                g_col1, g_col2 = st.columns([4, 6])
                with g_col1:
                    st.metric(
                        label="🇮🇳 Highest Searching City in India",
                        value=str(top_city[city_col]),
                        delta=f"{int(top_city[users_geo_col]):,} Active Users / Search Volume"
                    )
                    st.caption("City level traffic volume isolated for prospective applicants in India.")
                
                with g_col2:
                    fig_city = px.bar(
                        city_agg.head(10),
                        x=users_geo_col,
                        y=city_col,
                        orientation="h",
                        title="Top 10 Indian Cities by Search & Traffic Volume",
                        color=users_geo_col,
                        color_continuous_scale="Blues",
                        text_auto=",.0f"
                    )
                    fig_city.update_layout(height=320, yaxis={"categoryorder": "total ascending"}, margin=dict(l=120, r=20, t=30, b=20))
                    st.plotly_chart(fig_city, width="stretch")

    if not geo_data_available and not df_countries.empty:
        c_col = "Country" if "Country" in df_countries.columns else df_countries.columns[0]
        cl_col = "Clicks" if "Clicks" in df_countries.columns else df_countries.columns[1]
        
        india_row = df_countries[df_countries[c_col].astype(str).str.lower() == "india"]
        if not india_row.empty:
            st.metric(
                label="🇮🇳 Total Search Clicks from India",
                value=f"{int(india_row[cl_col].values[0]):,}",
                delta="Top Demand Country"
            )

    if not geo_data_available and df_countries.empty:
        st.info("💡 Upload `06_Geo_Global_GA4.csv` or `Countries.csv` to display India city-level search intelligence.")

    st.markdown("---")

    # --- CHART 6: WHAT COURSES ARE USERS SEARCHING FOR? (GSC Data) ---
    st.subheader(
        "🔎 What Course Keywords Are Users Searching on Google? (GSC Data)"
    )
    if not df_gsc.empty:
        q_col = "Query" if "Query" in df_gsc.columns else df_gsc.columns[0]
        imp_col = (
            "Impressions" if "Impressions" in df_gsc.columns else "Impressions"
        )
        click_col = "Clicks" if "Clicks" in df_gsc.columns else "Clicks"

        course_keywords = df_gsc[
            df_gsc[q_col]
            .astype(str)
            .str.contains(
                "course|btech|msc|bsc|mba|bba|phd|diploma|admission|fees|syllabus",
                case=False,
                na=False,
            )
        ]

        display_q = course_keywords if not course_keywords.empty else df_gsc
        top_queries = display_q.sort_values(by=imp_col, ascending=True).tail(12)

        fig_gsc = px.bar(
            top_queries,
            x=imp_col,
            y=q_col,
            orientation="h",
            color=click_col,
            labels={
                imp_col: "Google Search Impressions",
                q_col: "Search Query",
                click_col: "Organic Clicks",
            },
            color_continuous_scale="Cividis",
            text_auto=",.0f",
        )
        fig_gsc.update_layout(height=400, margin=dict(l=180, r=20, t=20, b=20))
        st.plotly_chart(fig_gsc, width="stretch")
    else:
        st.info(
            "💡 Upload `gsc_queries.csv` into `data/input/` to view prospective student search terms."
        )

    st.markdown("---")

    # --- PERFORMANCE QUADRANT & BENCHMARKS ---
    with st.expander("🎯 Extended Analytics: Performance Quadrant & CTR Benchmarks"):
        eq_col1, eq_col2 = st.columns(2)
        with eq_col1:
            fig_quad = px.scatter(
                course_agg,
                x="Sessions",
                y="CTR",
                color="Degree Level",
                hover_name="Course Title",
                title="Traffic Volume (Sessions) vs Engagement Rate (CTR %)",
                labels={"Sessions": "Sessions", "CTR": "Engagement Rate (%)"},
            )
            fig_quad.update_layout(
                height=380, margin=dict(l=20, r=20, t=30, b=20)
            )
            st.plotly_chart(fig_quad, width="stretch")

        with eq_col2:
            top5_ctr = course_agg.nlargest(5, "CTR")
            bot5_ctr = course_agg.nsmallest(5, "CTR")
            bench_df = pd.concat([top5_ctr, bot5_ctr]).sort_values(
                by="CTR", ascending=True
            )
            fig_bench = px.bar(
                bench_df,
                x="CTR",
                y="Course Title",
                orientation="h",
                color="CTR",
                title="Top 5 vs Bottom 5 Programs by Engagement Rate (%)",
                color_continuous_scale="RdYlGn",
            )
            fig_bench.update_layout(
                height=380, margin=dict(l=150, r=20, t=30, b=20)
            )
            st.plotly_chart(fig_bench, width="stretch")

    st.markdown("---")

    # --- AUDIT TABLE FOR ALL COURSES ---
    st.subheader(
        "📊 Individual Course Directory & Performance Table (~42–100 Courses)"
    )

    tf_col1, tf_col2 = st.columns([2, 1])
    with tf_col1:
        selected_deg = st.multiselect(
            "Filter Programs by Degree Level:",
            options=list(course_agg["Degree Level"].unique()),
            default=list(course_agg["Degree Level"].unique()),
        )
    with tf_col2:
        search_kw = st.text_input(
            "Search Program Title:", placeholder="e.g. Anesthesia, Radiology, BTech..."
        )

    filtered_courses = course_agg[
        course_agg["Degree Level"].isin(selected_deg)
    ].copy()

    if search_kw.strip():
        filtered_courses = filtered_courses[
            filtered_courses["Course Title"]
            .str.lower()
            .str.contains(search_kw.lower().strip())
        ]

    filtered_courses = filtered_courses.sort_values(by="Sessions", ascending=False)

    st.dataframe(
        filtered_courses[[
            "Course Title", "Degree Level", "Sessions", "Clicks", "CTR", "Conversions", "Lead Conv Rate (%)"
        ]],
        width="stretch",
        height=420,
        column_config={
            "Course Title": st.column_config.TextColumn("Course Directory Title"),
            "Degree Level": st.column_config.TextColumn("Degree Category"),
            "Sessions": st.column_config.NumberColumn("Sessions", format="%d"),
            "Clicks": st.column_config.NumberColumn("Clicks", format="%d"),
            "CTR": st.column_config.NumberColumn("CTR / Engagement (%)", format="%.2f%%"),
            "Conversions": st.column_config.NumberColumn("CTA Form Leads", format="%d"),
            "Lead Conv Rate (%)": st.column_config.NumberColumn("Lead Conv. Rate", format="%.2f%%"),
        },
    )

    # --- INTEGRATED CONVERSION & TRAFFIC DEEP-DIVE ---
    st.divider()
    st.subheader("📈 Course & Category Lead Conversion Analytics")

    top_conv_course = course_agg.sort_values(by="Lead Conv Rate (%)", ascending=False).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sessions", f"{course_agg['Sessions'].sum():,}")
    c2.metric("Total Clicks", f"{course_agg['Clicks'].sum():,}")
    c3.metric("Total CTA Form Leads", f"{course_agg['Conversions'].sum():,}")
    c4.metric(
        "🏆 Top Converting Course",
        f"{top_conv_course['Course Title']}",
        f"{top_conv_course['Lead Conv Rate (%)']:.2f}% Conv.",
    )

    # --- CATEGORY-WISE CONVERSION PERFORMANCE (Degree Level) ---
    st.markdown("#### 🏷️ Category-Wise (Degree Level) Conversion Performance")
    
    cat_summary = (
        course_agg.groupby("Degree Level")
        .agg(
            Total_Sessions=("Sessions", "sum"),
            Total_Clicks=("Clicks", "sum"),
            Total_Leads=("Conversions", "sum"),
            Avg_CTR=("CTR", "mean")
        )
        .reset_index()
    )

    # Clean fallback logic for Category Conversion Rate
    cat_traffic = np.where(
        cat_summary["Total_Sessions"] > 0,
        cat_summary["Total_Sessions"],
        np.where(cat_summary["Total_Clicks"] > 0, cat_summary["Total_Clicks"], 0)
    )

    cat_summary["Category Conv Rate (%)"] = np.where(
        cat_traffic > 0,
        (cat_summary["Total_Leads"] / cat_traffic) * 100,
        0.0
    ).round(2)

    cat_col1, cat_col2 = st.columns([6, 4])
    with cat_col1:
        fig_cat_conv = px.bar(
            cat_summary.sort_values(by="Category Conv Rate (%)", ascending=False),
            x="Degree Level",
            y="Category Conv Rate (%)",
            color="Degree Level",
            text_auto=".2f%",
            title="Conversion Rate by Course Degree Category (%)",
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_cat_conv.update_layout(height=350, showlegend=False, margin=dict(l=20, r=20, t=35, b=20))
        st.plotly_chart(fig_cat_conv, width="stretch")

    with cat_col2:
        st.dataframe(
            cat_summary[["Degree Level", "Total_Sessions", "Total_Clicks", "Total_Leads", "Category Conv Rate (%)"]],
            width="stretch",
            height=350,
            column_config={
                "Degree Level": st.column_config.TextColumn("Category"),
                "Total_Sessions": st.column_config.NumberColumn("Sessions", format="%d"),
                "Total_Clicks": st.column_config.NumberColumn("Clicks", format="%d"),
                "Total_Leads": st.column_config.NumberColumn("Leads", format="%d"),
                "Category Conv Rate (%)": st.column_config.NumberColumn("Conv. Rate", format="%.2f%%"),
            }
        )

    # --- INDIVIDUAL COURSE CONVERSION CHART ---
    if course_agg["Lead Conv Rate (%)"].max() == 0:
        st.info(
            "ℹ️ No lead conversion data recorded for these courses (all conversion rates are 0.00%). "
            "Upload a GA4 dataset with conversion events enabled to display this chart."
        )
    else:
        fig_course_conv = px.bar(
            course_agg.sort_values(by="Lead Conv Rate (%)", ascending=False).head(15),
            x="Lead Conv Rate (%)",
            y="Course Title",
            orientation="h",
            title="Top 15 Courses by CTA Form Lead Conversion Rate (%)",
            color="Lead Conv Rate (%)",
            color_continuous_scale="Viridis",
            text_auto=".2f%",
        )
        fig_course_conv.update_layout(height=450, margin=dict(l=180, r=20, t=30, b=20))
        st.plotly_chart(fig_course_conv, width="stretch")

else:
    st.info(
        "💡 Add `02_Course_GA4.csv` to `data/input/` to populate course intelligence."
    )