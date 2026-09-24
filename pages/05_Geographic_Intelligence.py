import io
import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Geographic Intelligence", layout="wide", page_icon="🌐"
)

st.title("🌐 Geographic & Location Intelligence")

GEO_DATA_PATH = "data/input/06_Geo_Global_GA4.csv"
GEO_PAGE_PATH = "data/input/06_Geo_PagePath_GA4.csv"


# 1. Primary Geo Data Loader
@st.cache_data(ttl=3600)
def load_geo_data(filepath):
    if not os.path.exists(filepath):
        return None, f"File not found at `{filepath}`"

    try:
        with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()

        start_idx = 0
        for i, line in enumerate(lines):
            line_str = line.strip()
            if line_str.startswith("#") or not line_str:
                continue
            if "," in line_str:
                start_idx = i
                break

        csv_content = "".join(lines[start_idx:])
        df = pd.read_csv(
            io.StringIO(csv_content), on_bad_lines="skip", engine="python"
        )

        df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]

        # Positional column mapping fallback
        first_col = str(df.columns[0]).lower()
        if "unnamed" in first_col or df.columns[0].isdigit():
            rename_dict = {
                df.columns[0]: "Country",
                df.columns[1]: "City",
            }
            if len(df.columns) > 2:
                rename_dict[df.columns[2]] = "Active users"
            if len(df.columns) > 3:
                rename_dict[df.columns[3]] = "Total users"
            if len(df.columns) > 8:
                rename_dict[df.columns[8]] = "Views"

            df = df.rename(columns=rename_dict)
        else:
            col_map = {}
            for c in df.columns:
                cl = c.lower()
                if "country" in cl and "Country" not in col_map.values():
                    col_map[c] = "Country"
                elif (
                    "city" in cl or "town" in cl
                ) and "City" not in col_map.values():
                    col_map[c] = "City"
                elif (
                    "active" in cl or "user" in cl
                ) and "Active users" not in col_map.values():
                    col_map[c] = "Active users"

            df = df.rename(columns=col_map)

        if "Country" in df.columns:
            df = df[~df["Country"].astype(str).str.startswith("#")].copy()
            df = df.dropna(subset=["Country"]).copy()

        if "Country" in df.columns:
            df["Country"] = (
                df["Country"]
                .astype(str)
                .str.strip()
                .replace(["(not set)", "not set", "nan", "None"], "Unknown")
            )
        if "City" in df.columns:
            df["City"] = (
                df["City"]
                .astype(str)
                .str.strip()
                .replace(
                    ["(not set)", "not set", "nan", "None"], "Unknown / Unmapped"
                )
            )

        for col in df.columns:
            if col not in ["Country", "City"]:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",", "").str.strip(),
                    errors="coerce",
                ).fillna(0)

        return df, None
    except Exception as e:
        return None, str(e)


# 2. Secondary City + Page Path Data Loader
@st.cache_data(ttl=3600)
def load_geo_page_data(filepath):
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()

        start_idx = 0
        for i, line in enumerate(lines):
            line_str = line.strip()
            if line_str.startswith("#") or not line_str:
                continue
            if "," in line_str:
                start_idx = i
                break

        csv_content = "".join(lines[start_idx:])
        df = pd.read_csv(
            io.StringIO(csv_content), on_bad_lines="skip", engine="python"
        )
        df.columns = [
            str(c).replace("\ufeff", "").strip().lower() for c in df.columns
        ]

        city_col = next((c for c in df.columns if "city" in c), None)
        path_col = next(
            (c for c in df.columns if "page" in c or "path" in c or "landing" in c),
            None,
        )
        user_col = next(
            (c for c in df.columns if "user" in c or "active" in c or "views" in c),
            None,
        )

        if not city_col or not path_col or not user_col:
            # Fallback to positional mapping
            city_col = df.columns[0]
            path_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            user_col = df.columns[2] if len(df.columns) > 2 else df.columns[-1]

        res_df = pd.DataFrame(
            {
                "City": df[city_col].astype(str).str.strip(),
                "PagePath": df[path_col].astype(str).str.strip(),
                "Users": pd.to_numeric(
                    df[user_col].astype(str).str.replace(",", ""), errors="coerce"
                ).fillna(0),
            }
        )
        return res_df
    except Exception:
        return None


df_geo, err_msg = load_geo_data(GEO_DATA_PATH)
df_geo_page = load_geo_page_data(GEO_PAGE_PATH)

# Inspector Expander
with st.expander("🔍 CSV Data Inspector"):
    if df_geo is not None:
        st.write("**Main Geo Columns:**", list(df_geo.columns))
        st.write(f"**Total Records Loaded:** {len(df_geo):,}")
        st.dataframe(df_geo.head(5))
    if df_geo_page is not None:
        st.write("**Page Path Geo Data Loaded:** Yes")
        st.dataframe(df_geo_page.head(5))
    else:
        st.write(
            "**Page Path Geo Data Loaded:** No (`data/input/06_Geo_PagePath_GA4.csv` not found)"
        )

if df_geo is None or df_geo.empty:
    st.error(
        f"⚠️ Unable to parse data from `{GEO_DATA_PATH}`. "
        "Please check that `06_Geo_Global_GA4.csv` is inside `data/input/`."
    )
else:
    country_col = "Country" if "Country" in df_geo.columns else None
    city_col = "City" if "City" in df_geo.columns else None
    user_col = "Active users" if "Active users" in df_geo.columns else None

    if not user_col:
        num_cols = df_geo.select_dtypes(include=["number"]).columns
        if len(num_cols) > 0:
            user_col = num_cols[0]

    if not country_col or not city_col or not user_col:
        st.warning(
            f"Could not automatically map columns. "
            f"Detected columns: `{list(df_geo.columns)}`."
        )
    else:
        # Aggregate traffic by country
        country_totals = (
            df_geo.groupby(country_col, as_index=False)[user_col]
            .sum()
            .sort_values(by=user_col, ascending=False)
            .reset_index(drop=True)
        )

        valid_map_df = country_totals[
            ~country_totals[country_col].str.lower().isin(["unknown", "not set"])
        ].copy()

        # ==========================================
        # SECTION 1: GLOBAL HEATMAP & TOP COUNTRIES
        # ==========================================
        head_col, toggle_col = st.columns([2, 1])
        with head_col:
            st.subheader("🌍 1. Global Traffic & Country Rankings")
        with toggle_col:
            exclude_india = st.checkbox(
                "🌍 Exclude India (Analyze International Traffic)",
                value=False,
                help="Check this box to remove India's skewed volume and reveal international market dynamics.",
            )

        display_country_df = valid_map_df.copy()
        if exclude_india:
            display_country_df = display_country_df[
                ~display_country_df[country_col].str.lower().eq("india")
            ].copy()

        display_country_df["Log_Volume"] = np.log10(
            display_country_df[user_col] + 1
        )

        total_disp_users = display_country_df[user_col].sum()
        top_disp_country = (
            display_country_df.iloc[0][country_col]
            if not display_country_df.empty
            else "N/A"
        )
        top_disp_vol = (
            display_country_df.iloc[0][user_col]
            if not display_country_df.empty
            else 0
        )

        col_g1, col_g2, col_g3 = st.columns(3)
        col_g1.metric(
            "Analyzed Scope Users",
            f"{int(total_disp_users):,}",
            delta="International Only" if exclude_india else "Global Total",
        )
        col_g2.metric(
            "Top Country in Scope",
            top_disp_country,
            delta=f"{int(top_disp_vol):,} Users",
        )
        col_g3.metric(
            "Countries Tracked", f"{len(display_country_df):,} Nations"
        )

        st.markdown("<br>", unsafe_allow_html=True)

        map_col, chart_col = st.columns([1.2, 1])

        with map_col:
            fig_world = px.choropleth(
                display_country_df,
                locations=country_col,
                locationmode="country names",
                color="Log_Volume",
                hover_name=country_col,
                hover_data={
                    "Log_Volume": False,
                    user_col: ":,",
                },
                color_continuous_scale="Viridis"
                if exclude_india
                else "Blues",
                title="Global Heatmap (Log-Scaled Visibility)",
                labels={user_col: "Active Users", "Log_Volume": "Traffic Scale"},
            )
            fig_world.update_layout(
                geo=dict(
                    showframe=False,
                    showcoastlines=True,
                    projection_type="natural earth",
                ),
                height=420,
                coloraxis_showscale=False,
                margin={"r": 0, "t": 40, "l": 0, "b": 0},
            )
            st.plotly_chart(fig_world, use_container_width=True)

        with chart_col:
            top_10_countries = display_country_df.head(10).sort_values(
                by=user_col, ascending=True
            )

            fig_top_countries = px.bar(
                top_10_countries,
                x=user_col,
                y=country_col,
                orientation="h",
                title="Top 10 Countries by Traffic Volume",
                text=user_col,
                color=user_col,
                color_continuous_scale="Blues",
            )
            fig_top_countries.update_traces(
                texttemplate="%{text:,}", textposition="outside"
            )
            fig_top_countries.update_layout(
                showlegend=False,
                height=420,
                xaxis_title="Active Users",
                yaxis_title="",
            )
            st.plotly_chart(fig_top_countries, use_container_width=True)

        st.divider()

        # ==========================================
        # SECTION 2: CITY-LEVEL BREAKDOWN BY COUNTRY
        # ==========================================
        st.subheader("📍 2. Country Selection & City-Level Segregation")

        all_sorted_countries = display_country_df[country_col].tolist()

        default_idx = 0
        if not exclude_india and "India" in all_sorted_countries:
            default_idx = all_sorted_countries.index("India")

        selected_country = st.selectbox(
            "Select Country for City Breakdown (Sorted by Traffic Volume):",
            options=all_sorted_countries,
            index=default_idx,
        )

        country_df = (
            df_geo[df_geo[country_col] == selected_country]
            .groupby(city_col, as_index=False)[user_col]
            .sum()
            .sort_values(by=user_col, ascending=False)
            .reset_index(drop=True)
        )

        named_cities_df = country_df[
            ~country_df[city_col].str.lower().str.contains("unknown")
        ]

        if not country_df.empty:
            total_country_users = country_df[user_col].sum()
            top_5_df = (
                named_cities_df.head(5)
                if not named_cities_df.empty
                else country_df.head(5)
            )

            top_1_city = top_5_df.iloc[0][city_col]
            top_1_vol = top_5_df.iloc[0][user_col]

            top_5_users = top_5_df[user_col].sum()
            concentration_pct = (
                (top_5_users / total_country_users * 100)
                if total_country_users > 0
                else 0
            )

            top_5_formatted = ", ".join(
                [
                    f"**{row[city_col]}** ({int(row[user_col]):,})"
                    for _, row in top_5_df.iterrows()
                ]
            )

            lead_insight = ""
            if len(top_5_df) >= 2:
                top_2_city = top_5_df.iloc[1][city_col]
                top_2_vol = top_5_df.iloc[1][user_col]
                gap_pct = (
                    ((top_1_vol - top_2_vol) / top_2_vol * 100)
                    if top_2_vol > 0
                    else 0
                )
                lead_insight = (
                    f"• **Market Lead Gap**: **{top_1_city}** leads **{top_2_city}** by **{gap_pct:.1f}%** in traffic volume, "
                    f"serving as the primary hub in {selected_country}."
                )

            # --- KEY TAKEAWAYS BANNER ---
            st.success(
                f"🏆 **Top 5 Cities in {selected_country}**: {top_5_formatted}\n\n"
                f"💡 **Key Regional Insights**:\n"
                f"• **Urban Concentration**: The top 5 cities generate **{concentration_pct:.1f}%** of total device traffic in {selected_country}.\n"
                f"{lead_insight}"
            )

            # City Metric Cards
            col1, col2, col3 = st.columns(3)
            col1.metric("Selected Country", selected_country)
            col2.metric(
                f"Highest Traffic City ({selected_country})",
                top_1_city,
                delta=f"{int(top_1_vol):,} {user_col}",
            )
            col3.metric(
                "Total Cities Tracked", f"{len(country_df):,} locations"
            )

            st.markdown("<br>", unsafe_allow_html=True)

            left_col, right_col = st.columns([1, 2])

            with left_col:
                st.markdown(f"#### Top Cities in {selected_country}")
                st.dataframe(
                    country_df[[city_col, user_col]].head(15),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        city_col: "City Name",
                        user_col: st.column_config.NumberColumn(
                            f"{user_col}", format="%d"
                        ),
                    },
                )

            with right_col:
                top_chart_df = country_df.head(10).sort_values(
                    by=user_col, ascending=True
                )

                fig_city = px.bar(
                    top_chart_df,
                    x=user_col,
                    y=city_col,
                    orientation="h",
                    title=f"Top 10 Cities in {selected_country} by Traffic Volume",
                    text=user_col,
                    color=user_col,
                    color_continuous_scale="Blues",
                )
                fig_city.update_traces(
                    texttemplate="%{text:,}", textposition="outside"
                )
                fig_city.update_layout(
                    showlegend=False,
                    height=480,
                    xaxis_title=user_col,
                    yaxis_title="",
                )
                st.plotly_chart(fig_city, use_container_width=True)

            st.divider()

            # ==========================================
            # SECTION 3: CITY CONTENT INTENT (BLOG vs COURSE)
            # ==========================================
            st.subheader(
                "🎯 3. City Content Intent Segregation (Blogs vs. Courses)"
            )

            city_list = country_df[city_col].tolist()
            selected_city = st.selectbox(
                f"Select City in {selected_country} to Analyze Content Intent:",
                options=city_list,
                index=0,
            )

            if df_geo_page is not None and not df_geo_page.empty:
                # Filter page paths for selected city
                city_paths = df_geo_page[
                    df_geo_page["City"]
                    .astype(str)
                    .str.lower()
                    .eq(selected_city.lower())
                ].copy()

                if not city_paths.empty:

                    def categorize_path(path):
                        p = str(path).lower()
                        if any(
                            k in p
                            for k in [
                                "/blog",
                                "/article",
                                "/news",
                                "/guide",
                                "/read",
                            ]
                        ):
                            return "Blog Content"
                        elif any(
                            k in p
                            for k in [
                                "/course",
                                "/program",
                                "/degree",
                                "/apply",
                                "/admission",
                                "/curriculum",
                            ]
                        ):
                            return "Course Content"
                        else:
                            return "General / Homepage"

                    city_paths["Category"] = city_paths["PagePath"].apply(
                        categorize_path
                    )
                    intent_df = (
                        city_paths.groupby("Category", as_index=False)["Users"]
                        .sum()
                        .sort_values(by="Users", ascending=False)
                    )

                    total_city_page_users = intent_df["Users"].sum()

                    c_left, c_right = st.columns([1, 1.2])

                    with c_left:
                        st.markdown(
                            f"#### Content Preference in **{selected_city}**"
                        )
                        st.dataframe(
                            intent_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Category": "Content Type",
                                "Users": st.column_config.NumberColumn(
                                    "Active Users", format="%d"
                                ),
                            },
                        )

                        blog_users = intent_df[
                            intent_df["Category"] == "Blog Content"
                        ]["Users"].sum()
                        course_users = intent_df[
                            intent_df["Category"] == "Course Content"
                        ]["Users"].sum()

                        blog_pct = (
                            (blog_users / total_city_page_users * 100)
                            if total_city_page_users > 0
                            else 0
                        )
                        course_pct = (
                            (course_users / total_city_page_users * 100)
                            if total_city_page_users > 0
                            else 0
                        )

                        # Decision Insight
                        if course_pct > blog_pct:
                            primary_intent = (
                                f"🎓 **High Transactional Intent**: Users in **{selected_city}** primarily explore "
                                f"**Course pages ({course_pct:.1f}%)**. Marketing should focus on direct course enrollment ads and lead forms."
                            )
                        elif blog_pct > course_pct:
                            primary_intent = (
                                f"📝 **High Top-of-Funnel Intent**: Users in **{selected_city}** predominantly consume "
                                f"**Blog content ({blog_pct:.1f}%)**. Focus on converting blog readers into leads via course call-to-action banners."
                            )
                        else:
                            primary_intent = f"⚖️ **Balanced Intent**: Equal distribution between blogs and courses in **{selected_city}**."

                        st.info(primary_intent)

                    with c_right:
                        fig_donut = px.pie(
                            intent_df,
                            names="Category",
                            values="Users",
                            hole=0.4,
                            title=f"Blog vs. Course Intent Breakdown for {selected_city}",
                            color_discrete_sequence=px.colors.qualitative.Pastel,
                        )
                        fig_donut.update_traces(
                            textinfo="percent+label",
                            hoverinfo="label+value+percent",
                        )
                        fig_donut.update_layout(height=380)
                        st.plotly_chart(fig_donut, use_container_width=True)
                else:
                    st.warning(
                        f"No specific page path records found for **{selected_city}** in `06_Geo_PagePath_GA4.csv`."
                    )
            else:
                # Setup Guide & Strategy Box when file is missing
                st.info(
                    f"💡 **To view whether users in {selected_city} hit Blogs vs Courses**:\n\n"
                    f"1. In GA4, create an Exploration report with **City** + **Page path**.\n"
                    f"2. Save the exported CSV as `06_Geo_PagePath_GA4.csv` inside `data/input/`.\n"
                    f"3. This section will automatically update with a real-time Blog vs Course donut chart and conversion intent decision breakdown!"
                )
        else:
            st.info(f"No city traffic recorded for {selected_country}.")