import re
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
    "daily time-series trends, device attribution, and Google search queries."
)

datasets = detect_and_load_all()
df_course = datasets.get("course", pd.DataFrame())
df_gsc = datasets.get("gsc_queries", pd.DataFrame())
df_device = datasets.get("device", pd.DataFrame())

# Course URL cleaning and categorization are centralized in src.data.normalizers.

if not df_course.empty:
    df = df_course.copy()

    # Robust page-column detection. Prefer the actual GA4 course export field.
    page_col = find_course_page_column(
        df,
        preferred=["Page path and screen class", "Page path", "URL"],
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
        exact_names=["Views", "Screen views"],
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
    events_col = first_column(
        exact_names=["Key events", "Conversions", "Event count"],
        keyword_groups=[("key", "events"), ("event", "count"), ("conversion",)],
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

    # --- 2. STRATEGIC HIGHLIGHTS ---
    if not df.empty and tot_sessions > 0:
        top_traffic = df.loc[df["Sessions"].idxmax()]
        top_ctr_idx = df["CTR"].idxmax()
        top_ctr_course = (
            df.loc[top_ctr_idx] if df["CTR"].max() > 0 else top_traffic
        )

        med_sess = df["Sessions"].median()
        opp_candidates = df[df["Sessions"] >= med_sess]
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
                f"• Sessions: **{int(top_traffic['Sessions']):,}** | Views: **{int(top_traffic['Views']):,}**"
            )
        with hc2:
            st.success(
                f"🔥 **Highest Engagement / CTR**\n\n**{top_ctr_course['Course Title']}**\n\n"
                f"• Engagement Rate: **{top_ctr_course['CTR']:.2f}%** | Events: **{int(top_ctr_course['Conversions']):,}**"
            )
        with hc3:
            st.warning(
                f"⚡ **CRO Priority Program**\n\n**{opp_course['Course Title']}**\n\n"
                f"High traffic (**{int(opp_course['Sessions']):,}** visits) with room for UX/CTA conversion optimization."
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
                    "Conversions": "sum",
                    "CTR": "mean",
                }
            )
            .reset_index()
        )

        for metric in ["Views", "Sessions", "Active Users", "Conversions"]:
            course_agg[metric] = (
                pd.to_numeric(course_agg[metric], errors="coerce")
                .fillna(0)
                .round(0)
                .astype("int64")
            )
        course_agg["CTR"] = (
            pd.to_numeric(course_agg["CTR"], errors="coerce").fillna(0).round(2)
        )

        top10_courses = course_agg.sort_values(by="Views", ascending=True).tail(
            10
        )
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

    # --- CHART 6: WHAT COURSES ARE USERS SEARCHING FOR? ---
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
        top_queries = display_q.sort_values(by=imp_col, ascending=True).tail(
            12
        )

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
        "📊 Individual Course Directory & Performance Table"
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
            "Search Program Title:", placeholder="e.g. Data Science, MBA..."
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

    filtered_courses = filtered_courses.sort_values(by="Views", ascending=False)

    st.dataframe(
        filtered_courses,
        width="stretch",
        height=400,
        column_config={
            "Views": st.column_config.NumberColumn("Views", format="%d"),
            "Sessions": st.column_config.NumberColumn("Sessions", format="%d"),
            "Active Users": st.column_config.NumberColumn("Active Users", format="%d"),
            "Conversions": st.column_config.NumberColumn("Conversions", format="%d"),
            "CTR": st.column_config.NumberColumn("CTR", format="%.2f"),
        },
    )

    # --- INTEGRATED CONVERSION & TRAFFIC DEEP-DIVE ---
    st.divider()
    st.subheader("📈 Course Lead Conversion Analytics")

    # Compute Lead Conversion Rate dynamically from real dataset
    course_agg["Lead Conv Rate (%)"] = (
        (course_agg["Conversions"] / course_agg["Sessions"]) * 100
    ).fillna(0).round(2)

    top_conv_course = course_agg.loc[course_agg["Lead Conv Rate (%)"].idxmax()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sessions", f"{course_agg['Sessions'].sum():,}")
    c2.metric("Total Active Applicants", f"{course_agg['Active Users'].sum():,}")
    c3.metric("Total Lead Conversions", f"{course_agg['Conversions'].sum():,}")
    c4.metric(
        "🏆 Top Converting Course",
        f"{top_conv_course['Course Title']}",
        f"{top_conv_course['Lead Conv Rate (%)']:.2f}% Conv.",
    )

    st.markdown("#### Course-Wise Conversion Performance")
    st.dataframe(
        course_agg[
            ["Course Title", "Degree Level", "Sessions", "Conversions", "CTR", "Lead Conv Rate (%)"]
        ],
        width="stretch",
        column_config={
            "Sessions": st.column_config.NumberColumn("Sessions", format="%d"),
            "Conversions": st.column_config.NumberColumn("Leads / Conversions", format="%d"),
            "CTR": st.column_config.NumberColumn("Engagement Rate (%)", format="%.2f%%"),
            "Lead Conv Rate (%)": st.column_config.NumberColumn("Lead Conv. Rate", format="%.2f%%"),
        },
    )

    # --- ADDED FALLBACK CHECK HERE ---
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
            title="Top 15 Courses by Lead Conversion Rate (%)",
            color="Lead Conv Rate (%)",
            color_continuous_scale="Viridis",
            text_auto=".2f",
        )
        fig_course_conv.update_layout(height=450, margin=dict(l=180, r=20, t=30, b=20))
        st.plotly_chart(fig_course_conv, width="stretch")

else:
    st.info(
        "💡 Add `02_Course_GA4.csv` to `data/input/` to populate course intelligence. "
        "The loader now keeps `03_Course_Performance.csv` separate."
    )