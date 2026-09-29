"""
11_Regional_CTR_Intelligence.py
Regional traffic breakdown (GA4 + GSC) for Blog & Course.
Focuses on Indian Cities (86%+ of traffic and 93%+ of search clicks) alongside Global Reach and Page CTR.
"""
import re
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

# — styles —
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
html, body, [class*="css"] { font-family:"Inter",sans-serif; }

div[data-testid="metric-container"] {
    background:linear-gradient(135deg,#1e293b,#0f172a);
    border:1px solid #334155; border-radius:12px; padding:16px 20px;
    box-shadow:0 4px 12px rgba(0,0,0,0.4);
}
div[data-testid="metric-container"] label {
    color:#94a3b8!important; font-size:11px!important;
    text-transform:uppercase; letter-spacing:.07em;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color:#f1f5f9!important; font-size:24px!important; font-weight:700!important;
}
.section-hdr {
    font-size:17px; font-weight:700; color:#38bdf8;
    border-left:4px solid #38bdf8; padding-left:10px;
    margin:28px 0 12px 0;
}
</style>
""", unsafe_allow_html=True)

st.title("🌍 Regional & CTR Intelligence")
st.caption("Traffic origin, engagement, and conversion performance across Indian cities (GA4) combined with organic CTR per page and region (GSC).")

from src.data.db_loader import load_file_or_db

DATA_DIR = Path("data/processed")

# — LOADERS —
@st.cache_data
def load_geo_global() -> pd.DataFrame:
    df = load_file_or_db("06_Geo_Global_GA4.parquet")
    if df.empty:
        return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    df = df[df.iloc[:, 0].astype(str).str.strip().ne("")].copy()
    
    col_map = {
        "Country": "Country",
        "City": "City",
        "Active users": "Active Users",
        "New users": "New Users",
        "Engaged sessions": "Engaged Sessions",
        "Engagement rate": "Engagement Rate",
        "Event count": "Event Count",
        "Key events": "Key Events",
        "User key event rate": "Key Event Rate"
    }
    df.rename(columns=col_map, inplace=True)
    
    for c in ["Active Users", "New Users", "Engaged Sessions", "Event Count", "Key Events"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0).astype(int)
            
    if "Engagement Rate" in df.columns:
        df["Engagement Rate (%)"] = pd.to_numeric(df["Engagement Rate"], errors="coerce").fillna(0) * 100
        
    return df

@st.cache_data
def load_city_devices() -> pd.DataFrame:
    return load_file_or_db("06_Geo_PagePath_GA4.parquet")

@st.cache_data
def load_gsc_countries(fname: str) -> pd.DataFrame:
    df = load_file_or_db(fname)
    if df.empty:
        return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    for col in ["Clicks", "Impressions", "Position"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0)
    if "CTR" in df.columns:
        df["CTR (%)"] = pd.to_numeric(
            df["CTR"].astype(str).str.replace("%", "", regex=False).str.strip(),
            errors="coerce"
        ).fillna(0)
    return df

@st.cache_data
def load_gsc_pages(fname: str) -> pd.DataFrame:
    df = load_file_or_db(fname)
    if df.empty:
        return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    page_col = next((c for c in df.columns if "page" in c.lower() or "top" in c.lower()), df.columns[0])
    df.rename(columns={page_col: "Page"}, inplace=True)
    df["Page Path"] = df["Page"].str.replace(r"^https?://[^/]+", "", regex=True).str.split("?").str[0]
    df["Label"] = (
        df["Page Path"]
        .str.replace(r"^/(blog|course|courses)/", "", regex=True)
        .str.replace(r"[-_]", " ", regex=True)
        .str.title()
        .str[:55]
    )
    for col in ["Clicks", "Impressions", "Position"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0)
    if "CTR" in df.columns:
        df["CTR (%)"] = pd.to_numeric(
            df["CTR"].astype(str).str.replace("%", "", regex=False).str.strip(),
            errors="coerce"
        ).fillna(0)
    return df

# — load all —
geo_df = load_geo_global()
city_devices = load_city_devices()
blog_ctry = load_gsc_countries("gsc_blog_countries.parquet")
course_ctry = load_gsc_countries("gsc_course_countries.parquet")
blog_pages_gsc = load_gsc_pages("gsc_blog_pages.parquet")
course_pages_gsc = load_gsc_pages("gsc_course_pages.parquet")

# Filter Indian cities data
india_cities_df = pd.DataFrame()
if not geo_df.empty:
    india_cities_df = geo_df[geo_df["Country"].str.strip().str.lower() == "india"].copy()
    india_cities_df = india_cities_df[~india_cities_df["City"].isin(["(not set)", ""])].copy()
    tot_ind_users = india_cities_df["Active Users"].sum()
    if tot_ind_users > 0:
        # 7,538 total GSC search clicks from India (6,652 Blog = 88.2%, 886 Course = 11.8%)
        india_cities_df["Est. Organic Clicks"] = ((india_cities_df["Active Users"] / tot_ind_users) * 7538).round().astype(int)
        india_cities_df["Est. Blog Clicks"] = (india_cities_df["Est. Organic Clicks"] * (6652 / 7538)).round().astype(int)
        india_cities_df["Est. Course Clicks"] = (india_cities_df["Est. Organic Clicks"] - india_cities_df["Est. Blog Clicks"]).clip(lower=0).astype(int)
    else:
        india_cities_df["Est. Organic Clicks"] = 0
        india_cities_df["Est. Blog Clicks"] = 0
        india_cities_df["Est. Course Clicks"] = 0
    india_cities_df["Lead Conv Rate (%)"] = (india_cities_df["Key Events"] / india_cities_df["Active Users"].clip(lower=1)) * 100

# — GLOBAL & DOMESTIC KPIs —
st.markdown('<div class="section-hdr">🇮🇳 High-Priority Domestic & Regional Overview</div>', unsafe_allow_html=True)

bc = int(blog_ctry["Clicks"].sum()) if not blog_ctry.empty else 0
cc = int(course_ctry["Clicks"].sum()) if not course_ctry.empty else 0
total_search_clicks = bc + cc
ind_search_clicks = 7538
ind_active_users = int(india_cities_df["Active Users"].sum()) if not india_cities_df.empty else 0
ind_leads = int(india_cities_df["Key Events"].sum()) if not india_cities_df.empty else 0
ind_avg_eng = float(india_cities_df["Engagement Rate (%)"].mean()) if not india_cities_df.empty else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("India Active Users", f"{ind_active_users:,}", help="86% of global traffic")
k2.metric("India Search Clicks", f"{ind_search_clicks:,}", help="93% of organic search clicks")
k3.metric("Indian Cities Tracked", f"{len(india_cities_df):,} Cities")
k4.metric("Total Admissions Leads", f"{ind_leads:,} Leads")
k5.metric("Avg Engagement Rate", f"{ind_avg_eng:.1f}%")
k6.metric("Global Countries", f"{len(blog_ctry)} Nations")

st.markdown("---")

# — TABS —
tab_india, tab_blog_geo, tab_course_geo, tab_blog_ctr, tab_course_ctr, tab_compare = st.tabs([
    "🇮🇳 Indian Cities - Traffic & Conversions",
    "🌍 Blog - Global Reach",
    "🎓 Course - Global Reach",
    "📝 Blog - CTR by Page",
    "🎯 Course - CTR by Page",
    "⚖️ Blog vs Course Comparison",
])

DARK = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
            font_color="#f1f5f9", margin=dict(l=10, r=10, t=45, b=10))

def _map(df, title):
    if df.empty: return None
    fig = px.choropleth(
        df, locations="Country", locationmode="country names",
        color="Clicks", hover_name="Country",
        hover_data={"Impressions": True, "CTR (%)": ":.2f", "Position": ":.1f"},
        color_continuous_scale="Blues",
        title=title,
    )
    fig.update_layout(
        **DARK, height=440,
        geo=dict(bgcolor="rgba(0,0,0,0)", showframe=False,
                 showcoastlines=True, coastlinecolor="#334155",
                 landcolor="#1e293b", oceancolor="#0f172a",
                 showocean=True, showcountries=True, countrycolor="#334155"),
        coloraxis_colorbar=dict(title="Clicks", tickfont=dict(color="#94a3b8")),
    )
    return fig

def _bar_country(df, x, y, color, title, n=20):
    top = df.nlargest(n, x)
    fig = px.bar(top, x=x, y=y, orientation="h", color=color,
                 color_continuous_scale="Blues" if "Clicks" in x else "RdYlGn",
                 title=title, text_auto=".2f" if "CTR" in x else ",.0f")
    fig.update_layout(**DARK, height=max(320, n*22),
                      yaxis=dict(autorange="reversed", gridcolor="#1e293b"),
                      xaxis=dict(gridcolor="#1e293b"), coloraxis_showscale=False)
    return fig

def _page_ctr_chart(df, n=20, title="CTR by Page"):
    top = df.nlargest(n, "Clicks")
    fig = px.scatter(
        top, x="Clicks", y="CTR (%)", size=top["Impressions"].clip(lower=1),
        color="CTR (%)", color_continuous_scale="RdYlGn",
        hover_name="Label",
        hover_data={"Impressions": True, "Position": ":.1f", "CTR (%)": ":.2f%"},
        title=title,
        labels={"Clicks": "Organic Clicks", "CTR (%)": "CTR (%)"},
    )
    fig.update_layout(**DARK, height=460,
                      xaxis=dict(gridcolor="#1e293b"), yaxis=dict(gridcolor="#1e293b"),
                      coloraxis_colorbar=dict(title="CTR %", tickfont=dict(color="#94a3b8")))
    return fig

# ——————————————————————————————————————————————————————————————————————
# TAB 1 - Indian Cities Performance (Primary Focus)
# ——————————————————————————————————————————————————————————————————————
with tab_india:
    if not india_cities_df.empty:
        col_ctrl1, col_ctrl2 = st.columns([1, 1.5])
        with col_ctrl1:
            top_n_cities = st.slider("Top N Indian Cities to Display", 10, 50, 15, key="top_ind_n")
        with col_ctrl2:
            rank_metric = st.selectbox(
                "Rank Indian Cities By:",
                options=["Active Users", "Key Events (Leads)", "Est. Organic Clicks", "Lead Conv Rate (%)"],
                index=0
            )

        col_metric_key = {
            "Active Users": "Active Users",
            "Key Events (Leads)": "Key Events",
            "Est. Organic Clicks": "Est. Organic Clicks",
            "Lead Conv Rate (%)": "Lead Conv Rate (%)"
        }[rank_metric]

        top_cities_ranked = india_cities_df.sort_values(col_metric_key, ascending=False).head(top_n_cities)

        # Bar Chart
        col_b1, col_b2 = st.columns([1.6, 1])
        with col_b1:
            fig_ind_bar = px.bar(
                top_cities_ranked,
                x=col_metric_key,
                y="City",
                orientation="h",
                color=col_metric_key,
                color_continuous_scale="Teal" if "Active" in rank_metric else "Viridis",
                title=f"Top {top_n_cities} Indian Cities by {rank_metric}",
                text_auto=".2f" if "%" in rank_metric else ",.0f"
            )
            fig_ind_bar.update_layout(
                **DARK,
                height=max(360, top_n_cities * 24),
                yaxis=dict(autorange="reversed", gridcolor="#1e293b"),
                xaxis=dict(gridcolor="#1e293b"),
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_ind_bar, use_container_width=True)

        with col_b2:
            st.markdown("#### High-Converting Regional Hubs")
            high_conv = india_cities_df[india_cities_df["Active Users"] >= 3000].sort_values("Lead Conv Rate (%)", ascending=False).head(8)
            st.dataframe(
                high_conv[["City", "Active Users", "Key Events", "Lead Conv Rate (%)"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Active Users": st.column_config.NumberColumn(format="%d"),
                    "Key Events": st.column_config.NumberColumn("Leads", format="%d"),
                    "Lead Conv Rate (%)": st.column_config.NumberColumn("Conv %", format="%.2f%%"),
                }
            )
            st.success("💡 **Strategic Finding**: **Ahmedabad (8.5%)**, **Gurugram (4.4%)**, and **Hyderabad (3.7%)** yield the highest lead-to-user conversion rates among major cities.")

        st.markdown("---")

        # City Deep Dive
        st.markdown("### 🔍 Specific City Funnel & Usability Deep-Dive")
        city_options = india_cities_df.sort_values("Active Users", ascending=False)["City"].tolist()
        def_city_idx = city_options.index("Bengaluru") if "Bengaluru" in city_options else 0
        sel_ind_city = st.selectbox("Select Indian City to Analyze:", options=city_options, index=def_city_idx)

        city_row = india_cities_df[india_cities_df["City"] == sel_ind_city].iloc[0]
        c_users = int(city_row["Active Users"])
        c_sessions = int(city_row["Engaged Sessions"])
        c_eng_rate = float(city_row["Engagement Rate (%)"])
        c_leads = int(city_row["Key Events"])
        c_conv = float(city_row["Lead Conv Rate (%)"])
        c_clicks = int(city_row["Est. Organic Clicks"])

        c_b_clicks = int(city_row.get("Est. Blog Clicks", round(c_clicks * 0.8825)))
        c_c_clicks = int(city_row.get("Est. Course Clicks", c_clicks - c_b_clicks))

        cd1, cd2, cd3, cd4, cd5, cd6 = st.columns(6)
        cd1.metric("Active Users", f"{c_users:,}")
        cd2.metric("Engaged Sessions", f"{c_sessions:,}")
        cd3.metric("Engagement Rate", f"{c_eng_rate:.1f}%")
        cd4.metric("Admissions Leads", f"{c_leads:,}")
        cd5.metric("Conversion Rate", f"{c_conv:.2f}%")
        cd6.metric("Total Search Clicks", f"{c_clicks:,}")

        # Channel Attribution Banner
        st.markdown(
            f'''<div style="background:#0f172a; border:1px solid #334155; border-radius:10px; padding:12px 18px; margin:16px 0;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                    <div>
                        <span style="color:#94a3b8; font-size:12px; text-transform:uppercase; letter-spacing:0.05em;">Channel Attribution for {sel_ind_city}:</span>
                        <div style="font-size:15px; font-weight:600; color:#f1f5f9; margin-top:2px;">
                            📝 <b>{c_b_clicks:,} Blog Search Visits</b> (88.2%) &nbsp;|&nbsp; 🎓 <b>{c_c_clicks:,} Direct Course Visits</b> (11.8%)
                        </div>
                    </div>
                    <div style="color:#38bdf8; font-size:13px;">
                        🎯 <b>{c_leads:,} Verified Admissions Inquiries / Leads Generated</b>
                    </div>
                </div>
            </div>''',
            unsafe_allow_html=True
        )

        # Device Breakdown for City
        if not city_devices.empty:
            match_dev = city_devices[city_devices["City"].astype(str).str.lower() == sel_ind_city.lower()]
            if not match_dev.empty:
                r_dev = match_dev.iloc[0]
                m_dev = int(r_dev.get("Mobile", 0))
                d_dev = int(r_dev.get("Desktop", 0))
                t_dev = int(r_dev.get("Tablet", 0))
                tot_dev = m_dev + d_dev + t_dev or 1
                
                col_city_l, col_city_r = st.columns([1, 1.2])
                with col_city_l:
                    st.markdown(f"#### Platform Usage in **{sel_ind_city}**")
                    dev_summary = pd.DataFrame([
                        {"Platform": "📱 Mobile", "Users": m_dev, "Share": f"{(m_dev/tot_dev)*100:.1f}%"},
                        {"Platform": "💻 Desktop", "Users": d_dev, "Share": f"{(d_dev/tot_dev)*100:.1f}%"},
                        {"Platform": "📟 Tablet", "Users": t_dev, "Share": f"{(t_dev/tot_dev)*100:.1f}%"},
                    ])
                    st.dataframe(dev_summary, hide_index=True, use_container_width=True)
                    if (d_dev / tot_dev) >= 0.25:
                        st.info(f"💼 **Corporate / Campus Evaluation**: Users in **{sel_ind_city}** have significant desktop participation ({(d_dev/tot_dev)*100:.1f}%), indicating thorough desktop evaluation.")
                    else:
                        st.info(f"📱 **Mobile First**: **{sel_ind_city}** is {(m_dev/tot_dev)*100:.1f}% mobile. Ensure frictionless 1-tap lead submission.")

                with col_city_r:
                    pie_df = pd.DataFrame([
                        {"Device": "Mobile", "Users": m_dev},
                        {"Device": "Desktop", "Users": d_dev},
                        {"Device": "Tablet", "Users": t_dev},
                    ])
                    pie_df = pie_df[pie_df["Users"] > 0]
                    fig_city_pie = px.pie(
                        pie_df, names="Device", values="Users", hole=0.45,
                        title=f"Platform Segregation for {sel_ind_city}",
                        color="Device",
                        color_discrete_map={"Mobile": "#38bdf8", "Desktop": "#10b981", "Tablet": "#f59e0b"}
                    )
                    fig_city_pie.update_layout(height=320, **DARK)
                    st.plotly_chart(fig_city_pie, use_container_width=True)

        st.markdown("---")
        st.markdown("#### Full Indian Cities Performance Table (2,396 Cities)")
        disp_ind = india_cities_df.sort_values("Active Users", ascending=False).copy()
        st.dataframe(
            disp_ind[["City", "Active Users", "Est. Organic Clicks", "Est. Blog Clicks", "Est. Course Clicks", "Engaged Sessions", "Engagement Rate (%)", "Key Events", "Lead Conv Rate (%)"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Active Users": st.column_config.NumberColumn(format="%d"),
                "Est. Organic Clicks": st.column_config.NumberColumn("Total Search", format="%d"),
                "Est. Blog Clicks": st.column_config.NumberColumn("Blog Search (88%)", format="%d"),
                "Est. Course Clicks": st.column_config.NumberColumn("Course Search (12%)", format="%d"),
                "Engaged Sessions": st.column_config.NumberColumn(format="%d"),
                "Engagement Rate (%)": st.column_config.NumberColumn("Eng. Rate", format="%.1f%%"),
                "Key Events": st.column_config.NumberColumn("Admissions Leads", format="%d"),
                "Lead Conv Rate (%)": st.column_config.NumberColumn("Conv %", format="%.2f%%"),
            }
        )
        st.download_button(
            "📥 Download Indian Cities Performance Data",
            disp_ind.to_csv(index=False).encode(),
            "indian_cities_performance.csv",
            "text/csv"
        )
    else:
        st.warning("No Indian cities data detected.")

# ——————————————————————————————————————————————————————————————————————
# TAB 2 - Blog Global Reach
# ——————————————————————————————————————————————————————————————————————
with tab_blog_geo:
    if not blog_ctry.empty:
        top_n = st.slider("Top N Countries to show", 10, min(len(blog_ctry), 50), 20, key="blog_geo_n")

        col_map, col_bar = st.columns([3, 2])
        with col_map:
            fig_m = _map(blog_ctry, "Blog Organic Clicks by Country")
            if fig_m: st.plotly_chart(fig_m, use_container_width=True)
        with col_bar:
            fig_b = _bar_country(blog_ctry, "Clicks", "Country", "Clicks",
                                  f"Top {top_n} Countries - Blog Clicks", top_n)
            st.plotly_chart(fig_b, use_container_width=True)

        st.markdown("---")
        st.markdown("#### Blog CTR by Country (Organic Search)")
        fig_ctr = _bar_country(blog_ctry.head(top_n), "CTR (%)", "Country",
                                "CTR (%)", f"Top {top_n} Countries - Blog CTR (%)", top_n)
        st.plotly_chart(fig_ctr, use_container_width=True)

        st.markdown("#### Full Country Data Table")
        disp = blog_ctry.sort_values("Clicks", ascending=False).copy()
        st.dataframe(disp.style.format({
            "Clicks": "{:,.0f}", "Impressions": "{:,.0f}",
            "CTR (%)": "{:.2f}%", "Position": "{:.1f}"
        }), hide_index=True, use_container_width=True,
        column_config={
            "Clicks": st.column_config.NumberColumn("Organic Clicks"),
            "Impressions": st.column_config.NumberColumn("Impressions"),
            "CTR (%)": st.column_config.NumberColumn("CTR (%)", format="%.2f%%"),
            "Position": st.column_config.NumberColumn("Avg Position", format="%.1f"),
        })
        st.download_button("📥 Download Blog Country Data",
                           blog_ctry.to_csv(index=False).encode(),
                           "blog_country_traffic.csv", "text/csv")
    else:
        st.info("No blog country data found.")

# ——————————————————————————————————————————————————————————————————————
# TAB 3 - Course Global Reach
# ——————————————————————————————————————————————————————————————————————
with tab_course_geo:
    if not course_ctry.empty:
        top_n2 = st.slider("Top N Countries", 10, min(len(course_ctry), 50), 20, key="course_geo_n")

        col_m, col_b = st.columns([3, 2])
        with col_m:
            fig_m2 = _map(course_ctry, "Course Organic Clicks by Country")
            if fig_m2: st.plotly_chart(fig_m2, use_container_width=True)
        with col_b:
            fig_b2 = _bar_country(course_ctry, "Clicks", "Country", "Clicks",
                                   f"Top {top_n2} Countries - Course Clicks", top_n2)
            st.plotly_chart(fig_b2, use_container_width=True)

        st.markdown("---")
        st.markdown("#### Course CTR by Country")
        fig_ctr2 = _bar_country(course_ctry.nlargest(top_n2, "Impressions"), "CTR (%)", "Country",
                                 "CTR (%)", f"Top {top_n2} by Impressions - Course CTR (%)", top_n2)
        st.plotly_chart(fig_ctr2, use_container_width=True)

        st.markdown("#### Full Country Data Table")
        disp2 = course_ctry.sort_values("Clicks", ascending=False).copy()
        st.dataframe(disp2.style.format({
            "Clicks": "{:,.0f}", "Impressions": "{:,.0f}",
            "CTR (%)": "{:.2f}%", "Position": "{:.1f}"
        }), hide_index=True, use_container_width=True)
        st.download_button("📥 Download Course Country Data",
                           course_ctry.to_csv(index=False).encode(),
                           "course_country_traffic.csv", "text/csv")
    else:
        st.info("No course country data found.")

# ——————————————————————————————————————————————————————————————————————
# TAB 4 - Blog CTR by Page
# ——————————————————————————————————————————————————————————————————————
with tab_blog_ctr:
    if not blog_pages_gsc.empty:
        top_np = st.slider("Top N Pages", 10, min(len(blog_pages_gsc), 50), 25, key="blog_page_n")

        st.markdown("#### Clicks vs CTR Bubble Chart (bubble size = Impressions)")
        fig_sc = _page_ctr_chart(blog_pages_gsc, top_np, "Blog Pages - Clicks vs CTR (Top by Clicks)")
        st.plotly_chart(fig_sc, use_container_width=True)

        st.markdown("---")
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### Highest CTR Blog Pages")
            top_ctr = blog_pages_gsc[blog_pages_gsc["Impressions"] > 100].nlargest(top_np, "CTR (%)")
            fig_tc = px.bar(top_ctr, x="CTR (%)", y="Label", orientation="h",
                            color="CTR (%)", color_continuous_scale="RdYlGn",
                            title=f"Top {top_np} Blog Pages by CTR (min 100 impressions)",
                            text_auto=".2f")
            fig_tc.update_layout(**DARK, height=max(340, top_np*22),
                                 yaxis=dict(autorange="reversed", gridcolor="#1e293b"),
                                 xaxis=dict(gridcolor="#1e293b"), coloraxis_showscale=False)
            st.plotly_chart(fig_tc, use_container_width=True)

        with col_r:
            st.markdown("#### Highest Impression Blog Pages (Visibility)")
            top_imp = blog_pages_gsc.nlargest(top_np, "Impressions")
            fig_imp = px.bar(top_imp, x="Impressions", y="Label", orientation="h",
                             color="CTR (%)", color_continuous_scale="RdYlGn",
                             title=f"Top {top_np} Blog Pages by Impressions",
                             text_auto=",.0f")
            fig_imp.update_layout(**DARK, height=max(340, top_np*22),
                                  yaxis=dict(autorange="reversed", gridcolor="#1e293b"),
                                  xaxis=dict(gridcolor="#1e293b"), coloraxis_showscale=True,
                                  coloraxis_colorbar=dict(title="CTR %", tickfont=dict(color="#94a3b8")))
            st.plotly_chart(fig_imp, use_container_width=True)

        st.markdown("---")
        st.markdown("#### Low CTR Opportunity Pages (High Impressions, Low CTR)")
        min_imp_b = st.slider("Min Impressions", 1000, 50000, 5000, step=1000, key="blog_opp_imp")
        max_ctr_b = st.slider("Max CTR (%)", 0.1, 3.0, 1.0, step=0.1, key="blog_opp_ctr")
        opp = blog_pages_gsc[(blog_pages_gsc["Impressions"] >= min_imp_b) & (blog_pages_gsc["CTR (%)"] <= max_ctr_b)].sort_values("Impressions", ascending=False)
        if not opp.empty:
            st.warning(f"**{len(opp)} opportunity pages** - high impressions but CTR below {max_ctr_b}%. Title rewrite recommended!")
            st.dataframe(opp[["Label", "Page Path", "Clicks", "Impressions", "CTR (%)", "Position"]].rename(
                columns={"Label": "Article", "Page Path": "URL Path"}),
                hide_index=True, use_container_width=True,
                column_config={"CTR (%)": st.column_config.NumberColumn("CTR (%)", format="%.2f%%"),
                                "Impressions": st.column_config.NumberColumn(format="%d"),
                                "Clicks": st.column_config.NumberColumn(format="%d"),
                                "Position": st.column_config.NumberColumn("Avg Pos", format="%.1f")})
        else:
            st.success("No opportunity pages found with current filters.")

        st.markdown("---")
        st.markdown("#### Full Blog GSC Table")
        st.dataframe(
            blog_pages_gsc[["Label", "Page Path", "Clicks", "Impressions", "CTR (%)", "Position"]]
            .sort_values("Clicks", ascending=False),
            hide_index=True, use_container_width=True,
            column_config={"CTR (%)": st.column_config.NumberColumn("CTR (%)", format="%.2f%%"),
                           "Impressions": st.column_config.NumberColumn(format="%d"),
                           "Clicks": st.column_config.NumberColumn(format="%d"),
                           "Position": st.column_config.NumberColumn("Avg Pos", format="%.1f")})
        st.download_button("📥 Download Blog Page CTR Data",
                           blog_pages_gsc.to_csv(index=False).encode(),
                           "blog_page_ctr.csv", "text/csv")
    else:
        st.info("No data found.")

# ——————————————————————————————————————————————————————————————————————
# TAB 5 - Course CTR by Page
# ——————————————————————————————————————————————————————————————————————
with tab_course_ctr:
    if not course_pages_gsc.empty:
        top_nc = st.slider("Top N Courses", 10, min(len(course_pages_gsc), 88), 20, key="course_page_n")

        st.markdown("#### Course Pages - Clicks vs CTR Bubble Chart")
        fig_sc2 = _page_ctr_chart(course_pages_gsc, top_nc, "Course Pages - Clicks vs CTR")
        st.plotly_chart(fig_sc2, use_container_width=True)

        st.markdown("---")
        col_l2, col_r2 = st.columns(2)
        with col_l2:
            st.markdown("#### Top Courses by Organic Clicks")
            fig_cc = px.bar(course_pages_gsc.nlargest(top_nc, "Clicks"),
                            x="Clicks", y="Label", orientation="h",
                            color="CTR (%)", color_continuous_scale="RdYlGn",
                            title=f"Top {top_nc} Course Pages by Clicks", text_auto=",.0f")
            fig_cc.update_layout(**DARK, height=max(340, top_nc*22),
                                 yaxis=dict(autorange="reversed", gridcolor="#1e293b"),
                                 xaxis=dict(gridcolor="#1e293b"),
                                 coloraxis_colorbar=dict(title="CTR %", tickfont=dict(color="#94a3b8")))
            st.plotly_chart(fig_cc, use_container_width=True)

        with col_r2:
            st.markdown("#### Top Courses by Impressions (Search Visibility)")
            fig_ci = px.bar(course_pages_gsc.nlargest(top_nc, "Impressions"),
                            x="Impressions", y="Label", orientation="h",
                            color="CTR (%)", color_continuous_scale="RdYlGn",
                            title=f"Top {top_nc} Course Pages by Impressions", text_auto=",.0f")
            fig_ci.update_layout(**DARK, height=max(340, top_nc*22),
                                 yaxis=dict(autorange="reversed", gridcolor="#1e293b"),
                                 xaxis=dict(gridcolor="#1e293b"),
                                 coloraxis_colorbar=dict(title="CTR %", tickfont=dict(color="#94a3b8")))
            st.plotly_chart(fig_ci, use_container_width=True)

        st.markdown("---")
        st.markdown("#### Full Course GSC Table")
        st.dataframe(
            course_pages_gsc[["Label", "Page Path", "Clicks", "Impressions", "CTR (%)", "Position"]]
            .sort_values("Clicks", ascending=False),
            hide_index=True, use_container_width=True,
            column_config={"CTR (%)": st.column_config.NumberColumn("CTR (%)", format="%.2f%%"),
                           "Impressions": st.column_config.NumberColumn(format="%d"),
                           "Clicks": st.column_config.NumberColumn(format="%d"),
                           "Position": st.column_config.NumberColumn("Avg Pos", format="%.1f")})
        st.download_button("📥 Download Course Page CTR Data",
                           course_pages_gsc.to_csv(index=False).encode(),
                           "course_page_ctr.csv", "text/csv")
    else:
        st.info("No course data found.")

# ——————————————————————————————————————————————————————————————————————
# TAB 6 - Blog vs Course Comparison
# ——————————————————————————————————————————————————————————————————————
with tab_compare:
    st.markdown("### Country Overlap: Which countries search for both Blog & Course content?")
    if not blog_ctry.empty and not course_ctry.empty:
        merged = pd.merge(
            blog_ctry[["Country", "Clicks", "Impressions", "CTR (%)"]].rename(
                columns={"Clicks": "Blog Clicks", "Impressions": "Blog Impressions", "CTR (%)": "Blog CTR (%)"}),
            course_ctry[["Country", "Clicks", "Impressions", "CTR (%)"]].rename(
                columns={"Clicks": "Course Clicks", "Impressions": "Course Impressions", "CTR (%)": "Course CTR (%)"}),
            on="Country", how="outer"
        ).fillna(0).sort_values("Blog Clicks", ascending=False)

        merged["Total Clicks"] = merged["Blog Clicks"] + merged["Course Clicks"]
        both = merged[(merged["Blog Clicks"] > 0) & (merged["Course Clicks"] > 0)]
        st.success(f"**{len(both)} countries** have organic clicks for BOTH Blog and Course content.")

        fig_comp = px.scatter(
            both, x="Blog Clicks", y="Course Clicks",
            size=both["Total Clicks"].clip(lower=1),
            color="Blog CTR (%)", color_continuous_scale="RdYlGn",
            hover_name="Country",
            hover_data={"Blog Impressions": True, "Course Impressions": True,
                        "Blog CTR (%)": ":.2f", "Course CTR (%)": ":.2f"},
            title="Countries: Blog Clicks vs Course Clicks (bubble = total clicks)",
        )
        fig_comp.update_layout(**DARK, height=500,
                               xaxis=dict(gridcolor="#1e293b"), yaxis=dict(gridcolor="#1e293b"),
                               coloraxis_colorbar=dict(title="Blog CTR %", tickfont=dict(color="#94a3b8")))
        st.plotly_chart(fig_comp, use_container_width=True)

        st.markdown("---")
        st.markdown("#### CTR Benchmark: Blog vs Course by Top Countries")
        top_countries = merged.nlargest(15, "Total Clicks")
        melt = pd.melt(
            top_countries, id_vars="Country",
            value_vars=["Blog CTR (%)", "Course CTR (%)"],
            var_name="Channel", value_name="CTR (%)"
        )
        fig_bar_comp = px.bar(
            melt, x="Country", y="CTR (%)", color="Channel", barmode="group",
            color_discrete_map={"Blog CTR (%)": "#38bdf8", "Course CTR (%)": "#a78bfa"},
            title="Blog vs Course CTR (%) - Top 15 Countries by Total Clicks",
        )
        fig_bar_comp.update_layout(**DARK, height=420,
                                   xaxis=dict(tickangle=-30, gridcolor="#1e293b"),
                                   yaxis=dict(gridcolor="#1e293b"),
                                   legend=dict(orientation="h", y=1.05))
        st.plotly_chart(fig_bar_comp, use_container_width=True)
