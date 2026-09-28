"""
11_Regional_CTR_Intelligence.py
Regional traffic breakdown (GA4 + GSC) for Blog & Course.
Includes: country heatmap, city bar, GSC CTR by country, CTR by blog page, CTR by course page.
"""
import re
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

# ─── styles ──────────────────────────────────────────────────────────────────
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
.tab-note {
    background:#0f172a; border:1px solid #1e3a5f; border-radius:8px;
    padding:8px 14px; font-size:13px; color:#7dd3fc; margin-bottom:14px;
}
</style>
""", unsafe_allow_html=True)

st.title("🌍 Regional & CTR Intelligence")
st.caption("Traffic origin by country and city (GA4) combined with organic CTR per region and page (GSC).")

DATA_DIR = Path("data/input")

# ─── LOADERS ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_geo_global() -> pd.DataFrame:
    """06_Geo_Global_GA4.csv — skip 9 comment lines, drop grand-total row."""
    p = DATA_DIR / "06_Geo_Global_GA4.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, encoding="utf-8-sig", skiprows=9, header=0,
                     on_bad_lines="skip", engine="python")
    df.columns = [c.strip() for c in df.columns]
    # Drop the blank / grand-total first row (both country & city empty)
    df = df[df.iloc[:, 0].astype(str).str.strip().ne("")].copy()
    df = df[df.iloc[:, 0].ne("(not set)")].copy()
    # Robust column rename
    cols = df.columns.tolist()
    rename = {}
    if len(cols) >= 1: rename[cols[0]] = "Country"
    if len(cols) >= 2: rename[cols[1]] = "City"
    if len(cols) >= 3: rename[cols[2]] = "Active Users"
    df.rename(columns=rename, inplace=True)
    df["Active Users"] = pd.to_numeric(
        df["Active Users"].astype(str).str.replace(",","",regex=False), errors="coerce"
    ).fillna(0).astype(int)
    return df[["Country","City","Active Users"]].copy()

@st.cache_data
def load_gsc_countries(fname: str) -> pd.DataFrame:
    p = DATA_DIR / fname
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    for col in ["Clicks","Impressions","Position"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",","",regex=False), errors="coerce"
            ).fillna(0)
    if "CTR" in df.columns:
        df["CTR (%)"] = pd.to_numeric(
            df["CTR"].astype(str).str.replace("%","",regex=False).str.strip(),
            errors="coerce"
        ).fillna(0)
    return df

@st.cache_data
def load_gsc_pages(fname: str) -> pd.DataFrame:
    p = DATA_DIR / fname
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    page_col = next((c for c in df.columns if "page" in c.lower() or "top" in c.lower()), df.columns[0])
    df.rename(columns={page_col: "Page"}, inplace=True)
    # Normalise URL to path
    df["Page Path"] = df["Page"].str.replace(r"^https?://[^/]+", "", regex=True).str.split("?").str[0]
    # Clean slug for readability
    df["Label"] = (
        df["Page Path"]
        .str.replace(r"^/(blog|course|courses)/", "", regex=True)
        .str.replace(r"[-_]", " ", regex=True)
        .str.title()
        .str[:55]
    )
    for col in ["Clicks","Impressions","Position"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",","",regex=False), errors="coerce"
            ).fillna(0)
    if "CTR" in df.columns:
        df["CTR (%)"] = pd.to_numeric(
            df["CTR"].astype(str).str.replace("%","",regex=False).str.strip(),
            errors="coerce"
        ).fillna(0)
    return df

# ── load all ──────────────────────────────────────────────────────────────────
geo_df          = load_geo_global()
blog_ctry       = load_gsc_countries("gsc_blog_countries.csv")
course_ctry     = load_gsc_countries("gsc_course_countries.csv")
blog_pages_gsc  = load_gsc_pages("gsc_blog_pages.csv")
course_pages_gsc= load_gsc_pages("gsc_course_pages.csv")

# ─── GLOBAL KPIs ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">🌐 Global Organic Reach (GSC)</div>', unsafe_allow_html=True)

bc = int(blog_ctry["Clicks"].sum())       if not blog_ctry.empty else 0
bi = int(blog_ctry["Impressions"].sum())  if not blog_ctry.empty else 0
cc = int(course_ctry["Clicks"].sum())     if not course_ctry.empty else 0
ci = int(course_ctry["Impressions"].sum()) if not course_ctry.empty else 0
bn = len(blog_ctry)
cn = len(course_ctry)
bavg_ctr = float(blog_ctry["CTR (%)"].mean())   if not blog_ctry.empty else 0
cavg_ctr = float(course_ctry["CTR (%)"].mean()) if not course_ctry.empty else 0

k1,k2,k3,k4,k5,k6,k7,k8 = st.columns(8)
k1.metric("Blog Countries",       f"{bn}")
k2.metric("Blog Org. Clicks",     f"{bc:,}")
k3.metric("Blog Impressions",     f"{bi:,}")
k4.metric("Blog Avg CTR",         f"{bavg_ctr:.2f}%")
k5.metric("Course Countries",     f"{cn}")
k6.metric("Course Org. Clicks",   f"{cc:,}")
k7.metric("Course Impressions",   f"{ci:,}")
k8.metric("Course Avg CTR",       f"{cavg_ctr:.2f}%")

st.markdown("---")

# ─── TABS ────────────────────────────────────────────────────────────────────
tab_blog_geo, tab_course_geo, tab_blog_ctr, tab_course_ctr, tab_compare = st.tabs([
    "📝 Blog — Regional Traffic",
    "🎓 Course — Regional Traffic",
    "📝 Blog — CTR by Page",
    "🎓 Course — CTR by Page",
    "📊 Blog vs Course Comparison",
])

# ── SHARED HELPERS ────────────────────────────────────────────────────────────
DARK = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
            font_color="#f1f5f9", margin=dict(l=10,r=10,t=45,b=10))

def _map(df, title):
    if df.empty: return None
    fig = px.choropleth(
        df, locations="Country", locationmode="country names",
        color="Clicks", hover_name="Country",
        hover_data={"Impressions":True, "CTR (%)": ":.2f", "Position":":.1f"},
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
        hover_data={"Impressions":True,"Position":":.1f","CTR (%)":":.2f%"},
        title=title,
        labels={"Clicks":"Organic Clicks","CTR (%)":"CTR (%)"},
    )
    fig.update_layout(**DARK, height=460,
                      xaxis=dict(gridcolor="#1e293b"), yaxis=dict(gridcolor="#1e293b"),
                      coloraxis_colorbar=dict(title="CTR %",tickfont=dict(color="#94a3b8")))
    return fig


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Blog Regional Traffic
# ════════════════════════════════════════════════════════════════════════════
with tab_blog_geo:
    st.markdown('<div class="tab-note">Source: GSC blog countries + GA4 geographic export. '
                'Clicks = organic clicks from that country.</div>', unsafe_allow_html=True)

    if not blog_ctry.empty:
        top_n = st.slider("Top N Countries to show", 10, min(len(blog_ctry),50), 20, key="blog_geo_n")

        col_map, col_bar = st.columns([3,2])
        with col_map:
            fig_m = _map(blog_ctry, "Blog Organic Clicks by Country")
            if fig_m: st.plotly_chart(fig_m, width="stretch")
        with col_bar:
            fig_b = _bar_country(blog_ctry, "Clicks", "Country", "Clicks",
                                  f"Top {top_n} Countries — Blog Clicks", top_n)
            st.plotly_chart(fig_b, width="stretch")

        st.markdown("---")

        # GA4 city breakdown
        if not geo_df.empty:
            st.markdown("#### Top Cities by Active Users (GA4)")
            top_cities = geo_df.groupby("City")["Active Users"].sum().reset_index()
            top_cities = top_cities[~top_cities["City"].isin(["(not set)",""])].nlargest(top_n,"Active Users")
            fig_city = px.bar(top_cities, x="Active Users", y="City", orientation="h",
                              color="Active Users", color_continuous_scale="Teal",
                              title=f"Top {top_n} Cities — Active Users (GA4)")
            fig_city.update_layout(**DARK, height=max(320,top_n*22),
                                   yaxis=dict(autorange="reversed",gridcolor="#1e293b"),
                                   xaxis=dict(gridcolor="#1e293b"), coloraxis_showscale=False)
            st.plotly_chart(fig_city, width="stretch")

        st.markdown("---")
        st.markdown("#### Blog CTR by Country (Organic Search)")
        fig_ctr = _bar_country(blog_ctry.head(top_n), "CTR (%)", "Country",
                                "CTR (%)", f"Top {top_n} Countries — Blog CTR (%)", top_n)
        st.plotly_chart(fig_ctr, width="stretch")

        st.markdown("#### Full Country Data Table")
        disp = blog_ctry.sort_values("Clicks", ascending=False).copy()
        st.dataframe(disp.style.format({
            "Clicks":"{:,.0f}","Impressions":"{:,.0f}",
            "CTR (%)":"{:.2f}%","Position":"{:.1f}"
        }), hide_index=True, width="stretch",
        column_config={
            "Clicks":     st.column_config.NumberColumn("Organic Clicks"),
            "Impressions":st.column_config.NumberColumn("Impressions"),
            "CTR (%)":    st.column_config.NumberColumn("CTR (%)", format="%.2f%%"),
            "Position":   st.column_config.NumberColumn("Avg Position", format="%.1f"),
        })
        st.download_button("📥 Download Blog Country Data",
                           blog_ctry.to_csv(index=False).encode(),
                           "blog_country_traffic.csv","text/csv")
    else:
        st.info("No blog country data found at `data/input/gsc_blog_countries.csv`.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — Course Regional Traffic
# ════════════════════════════════════════════════════════════════════════════
with tab_course_geo:
    st.markdown('<div class="tab-note">Source: GSC course countries. '
                'Shows which countries are searching for MSU courses.</div>', unsafe_allow_html=True)

    if not course_ctry.empty:
        top_n2 = st.slider("Top N Countries", 10, min(len(course_ctry),50), 20, key="course_geo_n")

        col_m, col_b = st.columns([3,2])
        with col_m:
            fig_m2 = _map(course_ctry, "Course Organic Clicks by Country")
            if fig_m2: st.plotly_chart(fig_m2, width="stretch")
        with col_b:
            fig_b2 = _bar_country(course_ctry, "Clicks", "Country", "Clicks",
                                   f"Top {top_n2} Countries — Course Clicks", top_n2)
            st.plotly_chart(fig_b2, width="stretch")

        st.markdown("---")
        st.markdown("#### Course CTR by Country")
        fig_ctr2 = _bar_country(course_ctry.nlargest(top_n2,"Impressions"), "CTR (%)", "Country",
                                 "CTR (%)", f"Top {top_n2} by Impressions — Course CTR (%)", top_n2)
        st.plotly_chart(fig_ctr2, width="stretch")

        st.markdown("#### Full Country Data Table")
        disp2 = course_ctry.sort_values("Clicks", ascending=False).copy()
        st.dataframe(disp2.style.format({
            "Clicks":"{:,.0f}","Impressions":"{:,.0f}",
            "CTR (%)":"{:.2f}%","Position":"{:.1f}"
        }), hide_index=True, width="stretch")
        st.download_button("📥 Download Course Country Data",
                           course_ctry.to_csv(index=False).encode(),
                           "course_country_traffic.csv","text/csv")
    else:
        st.info("No course country data at `data/input/gsc_course_countries.csv`.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — Blog CTR by Page
# ════════════════════════════════════════════════════════════════════════════
with tab_blog_ctr:
    st.markdown('<div class="tab-note">Source: GSC blog pages. CTR = Organic Clicks / Impressions. '
                'Low CTR + High Impressions = rewrite the page title/meta.</div>', unsafe_allow_html=True)

    if not blog_pages_gsc.empty:
        top_np = st.slider("Top N Pages", 10, min(len(blog_pages_gsc),50), 25, key="blog_page_n")

        # Scatter: Clicks vs CTR (bubble = impressions)
        st.markdown("#### Clicks vs CTR Bubble Chart (bubble size = Impressions)")
        fig_sc = _page_ctr_chart(blog_pages_gsc, top_np, "Blog Pages — Clicks vs CTR (Top by Clicks)")
        st.plotly_chart(fig_sc, width="stretch")

        st.markdown("---")

        # Bar: Top pages by CTR
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### Highest CTR Blog Pages")
            top_ctr = blog_pages_gsc[blog_pages_gsc["Impressions"]>100].nlargest(top_np,"CTR (%)")
            fig_tc = px.bar(top_ctr, x="CTR (%)", y="Label", orientation="h",
                            color="CTR (%)", color_continuous_scale="RdYlGn",
                            title=f"Top {top_np} Blog Pages by CTR (min 100 impressions)",
                            text_auto=".2f")
            fig_tc.update_layout(**DARK, height=max(340,top_np*22),
                                 yaxis=dict(autorange="reversed",gridcolor="#1e293b"),
                                 xaxis=dict(gridcolor="#1e293b"), coloraxis_showscale=False)
            st.plotly_chart(fig_tc, width="stretch")

        with col_r:
            st.markdown("#### Highest Impression Blog Pages (Visibility)")
            top_imp = blog_pages_gsc.nlargest(top_np,"Impressions")
            fig_imp = px.bar(top_imp, x="Impressions", y="Label", orientation="h",
                             color="CTR (%)", color_continuous_scale="RdYlGn",
                             title=f"Top {top_np} Blog Pages by Impressions",
                             text_auto=",.0f")
            fig_imp.update_layout(**DARK, height=max(340,top_np*22),
                                  yaxis=dict(autorange="reversed",gridcolor="#1e293b"),
                                  xaxis=dict(gridcolor="#1e293b"), coloraxis_showscale=True,
                                  coloraxis_colorbar=dict(title="CTR %",tickfont=dict(color="#94a3b8")))
            st.plotly_chart(fig_imp, width="stretch")

        st.markdown("---")
        st.markdown("#### Low CTR Opportunity Pages (High Impressions, Low CTR)")
        min_imp_b = st.slider("Min Impressions", 1000, 50000, 5000, step=1000, key="blog_opp_imp")
        max_ctr_b = st.slider("Max CTR (%)", 0.1, 3.0, 1.0, step=0.1, key="blog_opp_ctr")
        opp = blog_pages_gsc[(blog_pages_gsc["Impressions"]>=min_imp_b) & (blog_pages_gsc["CTR (%)"]<=max_ctr_b)].sort_values("Impressions",ascending=False)
        if not opp.empty:
            st.warning(f"**{len(opp)} opportunity pages** — high impressions but CTR below {max_ctr_b}%. Rewrite their titles!")
            st.dataframe(opp[["Label","Page Path","Clicks","Impressions","CTR (%)","Position"]].rename(
                columns={"Label":"Article","Page Path":"URL Path"}),
                hide_index=True, width="stretch",
                column_config={"CTR (%)":st.column_config.NumberColumn("CTR (%)",format="%.2f%%"),
                                "Impressions":st.column_config.NumberColumn(format="%d"),
                                "Clicks":st.column_config.NumberColumn(format="%d"),
                                "Position":st.column_config.NumberColumn("Avg Pos",format="%.1f")})
        else:
            st.success("No opportunity pages found with current filters.")

        st.markdown("---")
        st.markdown("#### Full Blog GSC Table")
        st.dataframe(
            blog_pages_gsc[["Label","Page Path","Clicks","Impressions","CTR (%)","Position"]]
            .sort_values("Clicks",ascending=False),
            hide_index=True, width="stretch",
            column_config={"CTR (%)":st.column_config.NumberColumn("CTR (%)",format="%.2f%%"),
                           "Impressions":st.column_config.NumberColumn(format="%d"),
                           "Clicks":st.column_config.NumberColumn(format="%d"),
                           "Position":st.column_config.NumberColumn("Avg Pos",format="%.1f")})
        st.download_button("📥 Download Blog Page CTR Data",
                           blog_pages_gsc.to_csv(index=False).encode(),
                           "blog_page_ctr.csv","text/csv")
    else:
        st.info("No data at `data/input/gsc_blog_pages.csv`.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — Course CTR by Page
# ════════════════════════════════════════════════════════════════════════════
with tab_course_ctr:
    st.markdown('<div class="tab-note">Source: GSC course pages (88 course URLs). '
                'CTR shows which programs attract clicks vs which need title optimisation.</div>',
                unsafe_allow_html=True)

    if not course_pages_gsc.empty:
        top_nc = st.slider("Top N Courses", 10, min(len(course_pages_gsc),88), 20, key="course_page_n")

        st.markdown("#### Course Pages — Clicks vs CTR Bubble Chart")
        fig_sc2 = _page_ctr_chart(course_pages_gsc, top_nc, "Course Pages — Clicks vs CTR")
        st.plotly_chart(fig_sc2, width="stretch")

        st.markdown("---")
        col_l2, col_r2 = st.columns(2)
        with col_l2:
            st.markdown("#### Top Courses by Organic Clicks")
            fig_cc = px.bar(course_pages_gsc.nlargest(top_nc,"Clicks"),
                            x="Clicks", y="Label", orientation="h",
                            color="CTR (%)", color_continuous_scale="RdYlGn",
                            title=f"Top {top_nc} Course Pages by Clicks", text_auto=",.0f")
            fig_cc.update_layout(**DARK, height=max(340,top_nc*22),
                                 yaxis=dict(autorange="reversed",gridcolor="#1e293b"),
                                 xaxis=dict(gridcolor="#1e293b"),
                                 coloraxis_colorbar=dict(title="CTR %",tickfont=dict(color="#94a3b8")))
            st.plotly_chart(fig_cc, width="stretch")

        with col_r2:
            st.markdown("#### Top Courses by Impressions (Search Visibility)")
            fig_ci = px.bar(course_pages_gsc.nlargest(top_nc,"Impressions"),
                            x="Impressions", y="Label", orientation="h",
                            color="CTR (%)", color_continuous_scale="RdYlGn",
                            title=f"Top {top_nc} Course Pages by Impressions", text_auto=",.0f")
            fig_ci.update_layout(**DARK, height=max(340,top_nc*22),
                                 yaxis=dict(autorange="reversed",gridcolor="#1e293b"),
                                 xaxis=dict(gridcolor="#1e293b"),
                                 coloraxis_colorbar=dict(title="CTR %",tickfont=dict(color="#94a3b8")))
            st.plotly_chart(fig_ci, width="stretch")

        st.markdown("---")
        st.markdown("#### Full Course GSC Table")
        st.dataframe(
            course_pages_gsc[["Label","Page Path","Clicks","Impressions","CTR (%)","Position"]]
            .sort_values("Clicks",ascending=False),
            hide_index=True, width="stretch",
            column_config={"CTR (%)":st.column_config.NumberColumn("CTR (%)",format="%.2f%%"),
                           "Impressions":st.column_config.NumberColumn(format="%d"),
                           "Clicks":st.column_config.NumberColumn(format="%d"),
                           "Position":st.column_config.NumberColumn("Avg Pos",format="%.1f")})
        st.download_button("📥 Download Course Page CTR Data",
                           course_pages_gsc.to_csv(index=False).encode(),
                           "course_page_ctr.csv","text/csv")
    else:
        st.info("No data at `data/input/gsc_course_pages.csv`.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — Blog vs Course Side-by-Side Comparison
# ════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.markdown('<div class="tab-note">Direct comparison of Blog vs Course organic performance '
                'by country and CTR benchmarks.</div>', unsafe_allow_html=True)

    st.markdown("### Country Overlap: Which countries search for both Blog & Course content?")
    if not blog_ctry.empty and not course_ctry.empty:
        merged = pd.merge(
            blog_ctry[["Country","Clicks","Impressions","CTR (%)"]].rename(
                columns={"Clicks":"Blog Clicks","Impressions":"Blog Impressions","CTR (%)":"Blog CTR (%)"}),
            course_ctry[["Country","Clicks","Impressions","CTR (%)"]].rename(
                columns={"Clicks":"Course Clicks","Impressions":"Course Impressions","CTR (%)":"Course CTR (%)"}),
            on="Country", how="outer"
        ).fillna(0).sort_values("Blog Clicks", ascending=False)

        merged["Total Clicks"] = merged["Blog Clicks"] + merged["Course Clicks"]
        both = merged[(merged["Blog Clicks"]>0) & (merged["Course Clicks"]>0)]
        st.success(f"**{len(both)} countries** have organic clicks for BOTH Blog and Course content.")

        fig_comp = px.scatter(
            both, x="Blog Clicks", y="Course Clicks",
            size=both["Total Clicks"].clip(lower=1),
            color="Blog CTR (%)", color_continuous_scale="RdYlGn",
            hover_name="Country",
            hover_data={"Blog Impressions":True,"Course Impressions":True,
                        "Blog CTR (%)":":.2f","Course CTR (%)":":.2f"},
            title="Countries: Blog Clicks vs Course Clicks (bubble = total clicks)",
        )
        fig_comp.update_layout(**DARK, height=500,
                               xaxis=dict(gridcolor="#1e293b"), yaxis=dict(gridcolor="#1e293b"),
                               coloraxis_colorbar=dict(title="Blog CTR %",tickfont=dict(color="#94a3b8")))
        st.plotly_chart(fig_comp, width="stretch")

        st.markdown("---")
        st.markdown("#### CTR Benchmark: Blog vs Course by Top Countries")
        top_countries = merged.nlargest(15,"Total Clicks")
        melt = pd.melt(
            top_countries, id_vars="Country",
            value_vars=["Blog CTR (%)","Course CTR (%)"],
            var_name="Channel", value_name="CTR (%)"
        )
        fig_bar_comp = px.bar(
            melt, x="Country", y="CTR (%)", color="Channel", barmode="group",
            color_discrete_map={"Blog CTR (%)":"#38bdf8","Course CTR (%)":"#a78bfa"},
            title="Blog vs Course CTR (%) — Top 15 Countries by Total Clicks",
        )
        fig_bar_comp.update_layout(**DARK, height=420,
                                   xaxis=dict(tickangle=-30,gridcolor="#1e293b"),
                                   yaxis=dict(gridcolor="#1e293b"),
                                   legend=dict(orientation="h",y=1.05))
        st.plotly_chart(fig_bar_comp, width="stretch")

        st.markdown("#### Full Combined Country Table")
        st.dataframe(
            merged[["Country","Blog Clicks","Blog Impressions","Blog CTR (%)","Course Clicks","Course Impressions","Course CTR (%)","Total Clicks"]]
            .sort_values("Total Clicks",ascending=False),
            hide_index=True, width="stretch",
            column_config={
                "Blog Clicks":    st.column_config.NumberColumn(format="%d"),
                "Blog Impressions":st.column_config.NumberColumn(format="%d"),
                "Blog CTR (%)":   st.column_config.NumberColumn(format="%.2f%%"),
                "Course Clicks":  st.column_config.NumberColumn(format="%d"),
                "Course Impressions":st.column_config.NumberColumn(format="%d"),
                "Course CTR (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Total Clicks":   st.column_config.NumberColumn(format="%d"),
            })
        st.download_button("📥 Download Combined Country Report",
                           merged.to_csv(index=False).encode(),
                           "blog_vs_course_countries.csv","text/csv")
    else:
        st.info("Need both `gsc_blog_countries.csv` and `gsc_course_countries.csv`.")
