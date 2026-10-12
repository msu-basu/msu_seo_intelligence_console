"""
02_Blog_Intelligence.py
-----------------------
Comprehensive Blog Intelligence Console featuring:
- Tab 1: Strategic Overview & 4-Quadrant Optimization Matrix
- Tab 2: Day-Wise & Month-Wise Trends (Custom Range & MoM Growth)
- Tab 3: Top Performing Blogs Leaderboard
- Tab 4: Blog Outlier & Viral Spike Intelligence
Optimized with Streamlit in-memory caching (@st.cache_data) for instantaneous sub-second chart rendering.
"""

from __future__ import annotations
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.data.db_loader import load_file_or_db
from src.analytics.blog_spikes import (
    prepare_clean_daily_df,
    get_day_wise_performance,
    get_month_wise_performance,
    get_top_performing_blogs,
    detect_blog_outliers,
)

# =============================================================================
# PAGE CONFIG & STYLES
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

# =============================================================================
# CONSTANTS & RATIOS
# =============================================================================
DATA_DIR = Path("data/processed")

FILTER_EXACT = {"/blog", "/blog/", "/", "(not set)", "", "/home", "/index", "/404"}
FILTER_REGEX = re.compile(
    r"(?:admin|edit|\.jpg|\.png|\.gif|\.pdf|\.css|\.js|\.xml|\.txt|/tag/|/category/|/page/\d|/author/)",
    re.IGNORECASE
)

VIEWS_SESSION_RATIO = 1.18
CTA_CLICK_RATE      = 0.20
LEAD_RATE           = 0.12
IMPRESSION_RATE     = 3.5


# =============================================================================
# HELPERS
# =============================================================================
def _strip_domain(url: str) -> str:
    u = re.sub(r"^https?://[^/]+", "", str(url).strip(), flags=re.IGNORECASE)
    u = u.split("?")[0].split("#")[0]
    return (u[:-1] if len(u) > 1 and u.endswith("/") else u) or "/"

def clean_title(path: str) -> str:
    c = _strip_domain(path)
    c = re.sub(r"^/blog/|^/course/|^/", "", c, flags=re.IGNORECASE)
    return c.replace("-", " ").replace("_", " ").title() or "Unknown"

def categorize_blog(path: str) -> str:
    p = str(path).lower()
    if any(kw in p for kw in ["career", "jobs", "salary", "scope", "placement"]):
        return "Career & Placement Guides"
    if any(kw in p for kw in ["result", "exam", "cbse", "12th", "10th", "cutoff"]):
        return "Exams & Results"
    if any(kw in p for kw in ["skills", "courses", "learn", "how-to", "paramedical"]):
        return "Skills & Course Guides"
    return "General Campus News"

def _pn(val) -> float:
    return pd.to_numeric(
        str(val).replace(",", "").replace("%", "").strip(), errors="coerce"
    ) or 0.0


# =============================================================================
# DATA LOADERS (CACHED)
# =============================================================================
@st.cache_data(show_spinner="Loading GA4 blog daily data...")
def load_raw_blog() -> pd.DataFrame:
    df = load_file_or_db("01_Blog_GA4.parquet")
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_gsc_pages() -> pd.DataFrame:
    df = load_file_or_db("gsc_blog_pages.parquet")
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_gsc_queries() -> pd.DataFrame:
    df = load_file_or_db("gsc_blog_queries.parquet")
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame()


# =============================================================================
# AGGREGATION PIPELINE
# =============================================================================
@st.cache_data(show_spinner=False)
def build_page_df(df_raw: pd.DataFrame, df_gsc: pd.DataFrame) -> pd.DataFrame:
    if df_raw.empty:
        return pd.DataFrame()

    pc = next(
        (c for c in df_raw.columns if c in [
            "Page path and screen class", "Page path", "Top pages",
            "Page", "Landing page", "Full page URL"
        ]), df_raw.columns[0]
    )

    def fc(cands): return next((c for c in cands if c in df_raw.columns), None)
    vc = fc(["Views", "Pageviews", "Event count"])
    ac = fc(["Active users", "Users"])
    ec = fc(["Event count"])
    kc = fc(["Key events", "Conversions"])

    for col in [vc, ac, ec, kc]:
        if col and col in df_raw.columns:
            df_raw[col] = df_raw[col].apply(_pn)

    agg = {}
    if vc: agg["Views"]        = (vc, "sum")
    if ac: agg["Active Users"] = (ac, "max")
    if ec: agg["Event Count"]  = (ec, "sum")
    if kc: agg["Key Events"]   = (kc, "sum")

    df = (
        df_raw.groupby(pc).agg(**agg)
        .reset_index().rename(columns={pc: "Page Path"})
    )

    df = df[~df["Page Path"].isin(FILTER_EXACT)].copy()
    df = df[~df["Page Path"].str.contains(FILTER_REGEX, na=False)].copy()

    v = df.get("Views", pd.Series(0, index=df.index))
    df["Sessions"] = np.maximum((v / VIEWS_SESSION_RATIO).round().astype(int), 1)

    if "CTA Clicks" not in df.columns:
        df["CTA Clicks"] = (df["Sessions"] * CTA_CLICK_RATE).round().astype(int)
    if "Key Events" in df.columns:
        df["Leads"] = df["Key Events"].astype(int)
    else:
        df["Leads"] = (df["CTA Clicks"] * LEAD_RATE).round().astype(int)

    if "Impressions" not in df.columns:
        df["Impressions"] = (v * IMPRESSION_RATE).round().astype(int)

    if not df_gsc.empty:
        gpc = next(
            (c for c in df_gsc.columns if "page" in c.lower() or "url" in c.lower()), None
        )
        if gpc:
            g = df_gsc.copy()
            g["_norm"] = g[gpc].apply(_strip_domain)
            if "CTR" in g.columns:
                g["GSC CTR (%)"] = (
                    g["CTR"].astype(str).str.replace("%", "", regex=False).str.strip()
                    .pipe(pd.to_numeric, errors="coerce").fillna(0.0)
                )
            for col in ["Clicks", "Impressions", "Position"]:
                if col in g.columns:
                    g[f"GSC {col}"] = (
                        g[col].astype(str).str.replace(",", "", regex=False)
                        .pipe(pd.to_numeric, errors="coerce").fillna(0)
                    )
            gcols = ["_norm"] + [c for c in g.columns if c.startswith("GSC ")]
            gsub = g[gcols].drop_duplicates(subset=["_norm"])
            df["_norm"] = df["Page Path"].apply(_strip_domain)
            df = pd.merge(df, gsub, on="_norm", how="left")
            df.drop(columns=["_norm"], inplace=True, errors="ignore")

            if "GSC Impressions" in df.columns:
                df["Impressions"] = np.where(
                    df["GSC Impressions"] > 0, df["GSC Impressions"], df["Impressions"]
                )

    df["Article Title"] = df["Page Path"].apply(clean_title)
    df["Category"]      = df["Page Path"].apply(categorize_blog)

    s = df["Sessions"].replace(0, np.nan)
    df["CTA CTR (%)"]  = (df["CTA Clicks"] / s * 100).fillna(0).round(2)
    df["Lead CVR (%)"] = (df["Leads"] / s * 100).fillna(0).round(2)
    c = df["CTA Clicks"].replace(0, np.nan)
    df["Click CVR (%)"]= (df["Leads"] / c * 100).fillna(0).round(2)

    return df.sort_values("Views", ascending=False).reset_index(drop=True)


# =============================================================================
# DATA INITIALIZATION
# =============================================================================
df_raw    = load_raw_blog()
df_gsc_pg = load_gsc_pages()
df_gsc_q  = load_gsc_queries()

if df_raw.empty:
    st.error("No blog dataset found in `data/input/`. Expected `01_Blog_GA4.parquet`.")
    st.stop()

df = build_page_df(df_raw, df_gsc_pg)

if df.empty:
    st.error("No valid article rows found after filtering.")
    st.stop()

# Clean daily-grain dataframe (Cached in RAM)
df_daily_clean = prepare_clean_daily_df(df_raw)

# =============================================================================
# HEADER & SIDEBAR FILTERS
# =============================================================================
st.title("📝 Blog Intelligence & Conversion Console")
st.caption("Comprehensive command centre for blog traffic performance, lead conversion modeling, daily trends, and viral outlier detection.")

st.sidebar.header("Blog Filters")
cats = sorted(df["Category"].unique())
sel_cats = st.sidebar.multiselect("Content Category", options=cats, default=cats)
max_v = max(int(df["Views"].max()), 10)
min_v = st.sidebar.number_input("Minimum Article Views", 0, max_v, 0, step=50)

fdf = df[df["Category"].isin(sel_cats) & (df["Views"] >= min_v)].copy()

# =============================================================================
# TOP-LEVEL NAVIGATION TABS (UNCLUTTERED ARCHITECTURE)
# =============================================================================
tab_strategy, tab_trends, tab_leaderboard, tab_outliers = st.tabs([
    "📊 Strategic Overview & Matrix",
    "📈 Day-Wise & Month-Wise Trends",
    "🏆 Top Performers Leaderboard",
    "🚨 Outlier & Viral Spikes"
])

# =============================================================================
# TAB 1: STRATEGIC OVERVIEW & 4-QUADRANT MATRIX
# =============================================================================
with tab_strategy:
    st.markdown("<div class='section-header'>Platform Scorecard</div>", unsafe_allow_html=True)

    ta = fdf["Article Title"].nunique()
    tv = int(fdf["Views"].sum())
    ts = int(fdf["Sessions"].sum())
    tc = int(fdf["CTA Clicks"].sum())
    tl = int(fdf["Leads"].sum())
    ac = (tc / ts * 100) if ts else 0.0
    av = (tl / ts * 100) if ts else 0.0

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Articles",    f"{ta:,}")
    k2.metric("Total Views",       f"{tv:,}")
    k3.metric("Est. Sessions",     f"{ts:,}", help="Views / 1.18")
    k4.metric("CTA Clicks",        f"{tc:,}", help="Sessions x 20%")
    k5.metric("Avg CTA CTR",       f"{ac:.1f}%")
    k6.metric("Leads / CVR",       f"{tl:,}  ({av:.1f}%)", help="CTA Clicks x 12%")

    st.markdown("---")

    # Readership Intelligence
    st.markdown("<div class='section-header'>Readership Intelligence</div>", unsafe_allow_html=True)
    cat_s = fdf.groupby("Category").agg(Views=("Views", "sum"), Articles=("Article Title", "nunique")).reset_index()
    c1, c2 = st.columns([1, 2])

    with c1:
        fig_pie = px.pie(cat_s, values="Views", names="Category", hole=0.45,
                         title="Views by Category",
                         color_discrete_sequence=px.colors.qualitative.Bold)
        fig_pie.update_traces(textinfo="percent+label", pull=[0.03]*len(cat_s))
        fig_pie.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", font_color="#f1f5f9",
                              title_font_color="#38bdf8", height=350,
                              margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        t10 = fdf.nlargest(10, "Views")
        fig_bar = px.bar(t10, x="Views", y="Article Title", orientation="h",
                         color="Category", title="Top 10 Articles by Views",
                         color_discrete_sequence=px.colors.qualitative.Bold)
        fig_bar.update_layout(yaxis=dict(autorange="reversed"),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#f1f5f9", title_font_color="#38bdf8", height=350,
                              margin=dict(l=10, r=10, t=50, b=10),
                              legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # Category Benchmarks
    st.markdown("<div class='section-header'>Category Benchmark Analysis</div>", unsafe_allow_html=True)
    cb = (fdf.groupby("Category").agg(
        Articles=("Article Title", "nunique"),
        Total_Views=("Views", "sum"),
        Total_Leads=("Leads", "sum"),
        Avg_CTR=("CTA CTR (%)", "mean"),
        Avg_CVR=("Lead CVR (%)", "mean"),
    ).reset_index().rename(columns={
        "Total_Views": "Total Views", "Total_Leads": "Total Leads",
        "Avg_CTR": "Avg CTA CTR (%)", "Avg_CVR": "Avg Lead CVR (%)",
    }))

    bm = cb.melt(id_vars="Category", value_vars=["Avg CTA CTR (%)", "Avg Lead CVR (%)"],
                 var_name="Metric", value_name="Value")
    fig_b = px.bar(bm, x="Category", y="Value", color="Metric", barmode="group",
                   title="Avg CTR vs CVR by Category",
                   color_discrete_map={"Avg CTA CTR (%)": "#38bdf8", "Avg Lead CVR (%)": "#a78bfa"})
    fig_b.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#f1f5f9", title_font_color="#38bdf8", height=330,
                        margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig_b, use_container_width=True)
    st.dataframe(cb.style.format({"Avg CTA CTR (%)": "{:.2f}%", "Avg Lead CVR (%)": "{:.2f}%",
                                   "Total Views": "{:,.0f}", "Total Leads": "{:,.0f}"}),
                 use_container_width=True, hide_index=True)

    st.markdown("---")

    # GSC Keyword Intelligence
    st.markdown("<div class='section-header'>Search Keyword Intelligence (GSC)</div>", unsafe_allow_html=True)
    if not df_gsc_q.empty:
        qc = next((c for c in df_gsc_q.columns if "quer" in c.lower() or "top" in c.lower()), df_gsc_q.columns[0])
        gq = df_gsc_q.copy()
        for col in ["Clicks", "Impressions", "Position"]:
            if col in gq.columns:
                gq[col] = (gq[col].astype(str).str.replace(",", "", regex=False)
                           .pipe(pd.to_numeric, errors="coerce").fillna(0))
        if "CTR" in gq.columns:
            gq["CTR (%)"] = (gq["CTR"].astype(str).str.replace("%", "", regex=False).str.strip()
                             .pipe(pd.to_numeric, errors="coerce").fillna(0))
        tq = (gq.rename(columns={qc: "Search Query"}).nlargest(15, "Clicks")
              [["Search Query", "Clicks", "Impressions", "CTR (%)", "Position"]])
        cq1, cq2 = st.columns([2, 3])
        with cq1:
            st.markdown("**Top 15 Organic Queries by Clicks**")
            st.dataframe(tq.style.format({"Clicks": "{:,.0f}", "Impressions": "{:,.0f}",
                                           "CTR (%)": "{:.2f}%", "Position": "{:.1f}"}),
                         use_container_width=True, hide_index=True, height=380)
        with cq2:
            fkw = px.bar(tq, x="Clicks", y="Search Query", orientation="h",
                         color="Clicks", color_continuous_scale="Blues",
                         title="Top Organic Keywords by Clicks")
            fkw.update_layout(yaxis=dict(autorange="reversed"),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#f1f5f9", title_font_color="#38bdf8", height=380,
                              margin=dict(l=10, r=10, t=50, b=10), coloraxis_showscale=False)
            st.plotly_chart(fkw, use_container_width=True)
    else:
        st.info("GSC queries file not found at `data/input/gsc_blog_queries.parquet`.")

    st.markdown("---")

    # 4-Quadrant Matrix
    st.markdown("<div class='section-header'>Strategic 4-Quadrant Optimization Matrix</div>", unsafe_allow_html=True)
    ps = (fdf.groupby(["Article Title", "Category"]).agg(
        Views=("Views", "sum"), Sessions=("Sessions", "sum"),
        CTA_Clicks=("CTA Clicks", "sum"), Leads=("Leads", "sum"),
        Impressions=("Impressions", "sum"),
    ).reset_index().rename(columns={"CTA_Clicks": "CTA Clicks"}))

    s2 = ps["Sessions"].replace(0, np.nan)
    ps["CTA CTR (%)"]  = (ps["CTA Clicks"] / s2 * 100).fillna(0).round(2)
    ps["Lead CVR (%)"] = (ps["Leads"] / s2 * 100).fillna(0).round(2)

    vt = float(np.maximum(ps["Views"].median(), 1))
    ct = float(ps["Lead CVR (%)"].median())

    cmap = {"Superstars": "#16a34a", "Hidden Gems": "#2563eb",
            "CRO Bottlenecks": "#d97706", "Underperformers": "#dc2626"}

    def _q(r):
        hv = r["Views"] >= vt
        hc = r["Lead CVR (%)"] >= ct
        if hv and hc:   return "Superstars"
        if not hv and hc: return "Hidden Gems"
        if hv and not hc: return "CRO Bottlenecks"
        return "Underperformers"

    ps["Quadrant"] = ps.apply(_q, axis=1)

    fsc = px.scatter(
        ps, x="Views", y="Lead CVR (%)", color="Quadrant",
        color_discrete_map=cmap, hover_name="Article Title",
        hover_data={"Views": True, "Lead CVR (%)": ":.2f%", "Leads": True, "Quadrant": True},
        title=f"Article Optimization Matrix (Thresholds: {vt:,.0f} Views | {ct:.1f}% Lead CVR)",
    )
    fsc.add_vline(x=vt, line_dash="dash", line_color="#64748b")
    fsc.add_hline(y=ct, line_dash="dash", line_color="#64748b")
    fsc.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                      font_color="#f1f5f9", title_font_color="#38bdf8", height=420,
                      margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fsc, use_container_width=True)

    qss = ps[ps["Quadrant"] == "Superstars"]
    qhg = ps[ps["Quadrant"] == "Hidden Gems"]
    qcb = ps[ps["Quadrant"] == "CRO Bottlenecks"]
    qup = ps[ps["Quadrant"] == "Underperformers"]

    qc1, qc2, qc3, qc4 = st.columns(4)
    qc1.metric("Superstars",     f"{len(qss)} Articles", f"{int(qss['Leads'].sum()):,} Leads")
    qc2.metric("Hidden Gems",    f"{len(qhg)} Articles", "Needs Promotion")
    qc3.metric("CRO Bottlenecks",f"{len(qcb)} Articles", "Fix CTAs Urgently")
    qc4.metric("Underperformers",f"{len(qup)} Articles", "Revamp / Merge")

    COLS = ["Article Title", "Category", "Views", "Sessions", "CTA CTR (%)", "Lead CVR (%)", "Leads"]
    t1, t2, t3, t4 = st.tabs(["CRO Bottlenecks", "Hidden Gems", "Superstars", "Underperformers"])
    with t1:
        st.warning("High readership but poor lead capture. Redesign CTAs, add embedded lead forms, improve mobile UX.")
        st.dataframe(qcb[COLS].sort_values("Views", ascending=False), use_container_width=True, hide_index=True)
    with t2:
        st.info("Strong conversion intent -- needs more traffic. Feature on homepage, add internal links, newsletters.")
        st.dataframe(qhg[COLS].sort_values("Lead CVR (%)", ascending=False), use_container_width=True, hide_index=True)
    with t3:
        st.success("Core lead drivers -- protect rankings! Keep content fresh, verify CTAs, monitor search position.")
        st.dataframe(qss[COLS].sort_values("Leads", ascending=False), use_container_width=True, hide_index=True)
    with t4:
        st.error("Low traffic and low conversion. Refresh keywords, consolidate similar articles, or prune/redirect.")
        st.dataframe(qup[COLS].sort_values("Views", ascending=True), use_container_width=True, hide_index=True)

    st.markdown("---")

    # Directory
    st.markdown("<div class='section-header'>Full Article Directory</div>", unsafe_allow_html=True)
    srch = st.text_input("Search articles by title or category:", key="strat_search")
    dd = ps.drop(columns=["Views_P"], errors="ignore").copy()
    if srch:
        dd = dd[dd["Article Title"].str.contains(srch, case=False, na=False)
               | dd["Category"].str.contains(srch, case=False, na=False)]

    st.dataframe(dd.sort_values("Views", ascending=False), use_container_width=True, hide_index=True,
                 column_config={
                     "Views":        st.column_config.NumberColumn(format="%d"),
                     "Sessions":     st.column_config.NumberColumn(format="%d"),
                     "CTA Clicks":   st.column_config.NumberColumn(format="%d"),
                     "CTA CTR (%)":  st.column_config.NumberColumn("CTA CTR", format="%.2f%%"),
                     "Leads":        st.column_config.NumberColumn(format="%d"),
                     "Lead CVR (%)": st.column_config.NumberColumn("Lead CVR", format="%.2f%%"),
                     "Impressions":  st.column_config.NumberColumn(format="%d"),
                 })

    st.download_button(label="Export Directory CSV",
                       data=dd.to_csv(index=False).encode("utf-8"),
                       file_name="blog_articles_directory.csv", mime="text/csv")


# =============================================================================
# TAB 2: DAY-WISE & MONTH-WISE TRENDS (INSTANT CACHED RENDERING)
# =============================================================================
with tab_trends:
    st.markdown("<div class='section-header'>📈 Day-Wise & Month-Wise Blog Performance</div>", unsafe_allow_html=True)
    st.caption("Granular daily trajectories, date range filtering, monthly volume distributions, and MoM growth acceleration.")

    if df_daily_clean.empty:
        st.info("Daily grain data is not available.")
    else:
        min_date = df_daily_clean["Date"].min().date()
        max_date = df_daily_clean["Date"].max().date()

        sub_tab_daily, sub_tab_monthly = st.tabs([
            "📅 Day-Wise Range Performance",
            "📆 Month-Wise Volume & MoM Growth"
        ])

        with sub_tab_daily:
            d_col1, d_col2 = st.columns([1, 2])
            with d_col1:
                date_range = st.date_input(
                    "Date Range Filter:",
                    value=[min_date, max_date],
                    min_value=min_date,
                    max_value=max_date,
                    key="tab_trends_date_range"
                )
            
            start_d = date_range[0] if isinstance(date_range, (list, tuple)) and len(date_range) > 0 else min_date
            end_d = date_range[1] if isinstance(date_range, (list, tuple)) and len(date_range) > 1 else max_date

            all_titles = sorted(df_daily_clean["Article Title"].unique().tolist())
            with d_col2:
                chosen_blogs = st.multiselect(
                    "Compare Specific Blogs (leave empty for Top 5):",
                    options=all_titles,
                    default=[],
                    key="tab_trends_chosen_blogs",
                    help="Overlay specific articles on the daily chart"
                )

            total_daily_df, per_blog_daily_df = get_day_wise_performance(
                df_daily_clean,
                start_date=start_d,
                end_date=end_d,
                selected_blogs_tuple=tuple(chosen_blogs) if chosen_blogs else ()
            )

            if not total_daily_df.empty:
                tot_range_views = int(total_daily_df["Views"].sum())
                avg_daily_v = round(total_daily_df["Views"].mean(), 1)
                peak_day_row = total_daily_df.loc[total_daily_df["Views"].idxmax()]
                peak_date_str = peak_day_row["Date"].strftime("%d %b %Y")
                peak_views_val = int(peak_day_row["Views"])

                m_c1, m_c2, m_c3, m_c4 = st.columns(4)
                m_c1.metric("Views in Range", f"{tot_range_views:,}")
                m_c2.metric("Avg Daily Views", f"{avg_daily_v:,}")
                m_c3.metric("Peak Daily Views", f"{peak_views_val:,}", f"on {peak_date_str}")
                m_c4.metric("Days Tracked", f"{len(total_daily_df):,}")

                fig_total_daily = px.line(
                    total_daily_df,
                    x="Date",
                    y=["Views", "Rolling_7d_Views"],
                    labels={"value": "Views", "Date": "Date", "variable": "Metric"},
                    title="Platform Daily Blog Views (with 7-Day Rolling Moving Average)",
                    color_discrete_map={"Views": "#38bdf8", "Rolling_7d_Views": "#f59e0b"},
                    template="plotly_dark"
                )
                fig_total_daily.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="#0f172a",
                    font_color="#f1f5f9",
                    height=350,
                    hovermode="x unified",
                    legend=dict(orientation="h", y=-0.2),
                    margin=dict(l=10, r=10, t=40, b=10)
                )
                st.plotly_chart(fig_total_daily, use_container_width=True)

                if not per_blog_daily_df.empty:
                    st.markdown("#### 🔍 Article-Level Trajectory Comparison")
                    fig_blog_daily = px.line(
                        per_blog_daily_df,
                        x="Date",
                        y="Views",
                        color="Article Title",
                        title="Daily Readership Trajectory by Article",
                        template="plotly_dark"
                    )
                    fig_blog_daily.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="#0f172a",
                        font_color="#f1f5f9",
                        height=360,
                        hovermode="x unified",
                        legend=dict(orientation="h", y=-0.3),
                        margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_blog_daily, use_container_width=True)

        with sub_tab_monthly:
            monthly_df = get_month_wise_performance(df_daily_clean)
            if not monthly_df.empty:
                mo_c1, mo_c2 = st.columns([3, 2])
                with mo_c1:
                    fig_monthly = px.bar(
                        monthly_df,
                        x="YearMonth",
                        y="Views",
                        text="Views",
                        title="Month-Wise Total Blog Views",
                        color="Views",
                        color_continuous_scale="Blues",
                        template="plotly_dark"
                    )
                    fig_monthly.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
                    fig_monthly.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="#0f172a",
                        font_color="#f1f5f9",
                        height=350,
                        coloraxis_showscale=False,
                        margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_monthly, use_container_width=True)

                with mo_c2:
                    fig_mom = px.line(
                        monthly_df.dropna(subset=["MoM_Growth_%"]),
                        x="YearMonth",
                        y="MoM_Growth_%",
                        markers=True,
                        title="Month-over-Month (MoM) Growth (%)",
                        color_discrete_sequence=["#10b981"],
                        template="plotly_dark"
                    )
                    fig_mom.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
                    fig_mom.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="#0f172a",
                        font_color="#f1f5f9",
                        height=350,
                        margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_mom, use_container_width=True)

                st.markdown("#### 📋 Monthly Performance Data Breakdown")
                disp_monthly = monthly_df.rename(columns={
                    "YearMonth": "Month",
                    "Views": "Total Views",
                    "Active_Users": "Peak Active Users",
                    "Articles_Active": "Active Articles",
                    "Avg_Daily_Views": "Avg Daily Views",
                    "MoM_Growth_%": "MoM Growth (%)"
                })
                st.dataframe(
                    disp_monthly.style.format({
                        "Total Views": "{:,.0f}",
                        "Peak Active Users": "{:,.0f}",
                        "Active Articles": "{:,.0f}",
                        "Avg Daily Views": "{:,.1f}",
                        "MoM Growth (%)": "{:+.1f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )


# =============================================================================
# TAB 3: TOP PERFORMERS LEADERBOARD
# =============================================================================
with tab_leaderboard:
    st.markdown("<div class='section-header'>🏆 Top Performing Blogs Leaderboard</div>", unsafe_allow_html=True)
    st.caption("Identifies standout articles across volume dominance, vertical category champions, and single-day surge impact.")

    top_perf = get_top_performing_blogs(df_daily_clean, top_n=10)
    vol_leaders = top_perf.get("volume_leaders", pd.DataFrame())
    cat_leaders = top_perf.get("category_leaders", pd.DataFrame())
    surge_leaders = top_perf.get("surge_leaders", pd.DataFrame())

    if not vol_leaders.empty:
        champion = vol_leaders.iloc[0]
        st.info(
            f"👑 **Standout Top Performer:** **{champion['Article Title']}** with "
            f"**{int(champion['Views']):,}** total views (avg **{champion['Avg_Daily_Views']}** views/day) "
            f"in vertical *{champion['Category']}*!"
        )

        lead_tab1, lead_tab2, lead_tab3 = st.tabs([
            "📊 All-Time Volume Leaders",
            "🥇 Best by Content Category",
            "⚡ Peak Single-Day Surge Leaders"
        ])

        with lead_tab1:
            fig_top_bar = px.bar(
                vol_leaders,
                x="Views",
                y="Article Title",
                orientation="h",
                color="Category",
                title=f"Top {len(vol_leaders)} Articles by Readership Volume",
                template="plotly_dark",
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_top_bar.update_layout(
                yaxis=dict(autorange="reversed"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#0f172a",
                font_color="#f1f5f9",
                height=360,
                legend=dict(orientation="h", y=-0.2),
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_top_bar, use_container_width=True)

            st.dataframe(
                vol_leaders[["Article Title", "Category", "Views", "Est_Sessions", "Avg_Daily_Views", "Peak_Single_Day_Views"]].rename(columns={
                    "Views": "Total Views",
                    "Est_Sessions": "Est. Sessions",
                    "Avg_Daily_Views": "Daily Avg",
                    "Peak_Single_Day_Views": "Peak Day"
                }),
                use_container_width=True,
                hide_index=True
            )

        with lead_tab2:
            st.markdown("#### 🏅 Standout Article for Each Content Category")
            st.dataframe(
                cat_leaders[["Category", "Article Title", "Views", "Est_Sessions", "Avg_Daily_Views"]].rename(columns={
                    "Views": "Category Top Views",
                    "Est_Sessions": "Est. Sessions",
                    "Avg_Daily_Views": "Daily Avg"
                }),
                use_container_width=True,
                hide_index=True
            )

        with lead_tab3:
            st.markdown("#### ⚡ Top Articles by Maximum Single-Day Readership Spike")
            st.dataframe(
                surge_leaders[["Article Title", "Category", "Peak_Single_Day_Views", "Views", "Avg_Daily_Views"]].rename(columns={
                    "Peak_Single_Day_Views": "Peak Single-Day Views",
                    "Views": "Total Views",
                    "Avg_Daily_Views": "Normal Daily Avg"
                }),
                use_container_width=True,
                hide_index=True
            )


# =============================================================================
# TAB 4: OUTLIER & VIRAL SPIKE INTELLIGENCE
# =============================================================================
with tab_outliers:
    st.markdown("<div class='section-header'>🚨 Blog Outlier & Viral Spike Intelligence</div>", unsafe_allow_html=True)
    st.caption(
        "Automated statistical anomaly detection (Z-score ≥ 3.0 or Surge Ratio ≥ 2.5x normal baseline). "
        "Records viral spikes, seasonal exam surges, and breaking demand events."
    )

    outliers_df = detect_blog_outliers(df_daily_clean, min_views=20, z_threshold=3.0, ratio_threshold=2.5)

    if not outliers_df.empty:
        tot_outliers = len(outliers_df)
        max_surge = outliers_df.sort_values("Spike_Views", ascending=False).iloc[0]
        max_mult = outliers_df.sort_values("Surge_Multiplier", ascending=False).iloc[0]

        ok1, ok2, ok3, ok4 = st.columns(4)
        ok1.metric("Outlier Events Detected", f"{tot_outliers}")
        ok2.metric("Highest Single-Day Views", f"{int(max_surge['Spike_Views'])} Views", f"on {max_surge['Date'].strftime('%d %b %Y')}")
        ok3.metric("Largest Surge Factor", f"{max_mult['Surge_Multiplier']}", f"{max_mult['Article Title'][:20]}...")
        ok4.metric("Algorithm", "Z-Score ≥ 3.0", "Rolling Baseline")

        # Scatter Timeline
        fig_outlier_time = px.scatter(
            outliers_df,
            x="Date",
            y="Spike_Views",
            size="Spike_Views",
            color="Category",
            hover_name="Article Title",
            hover_data={"Date": "|%d %b %Y", "Surge_Multiplier": True, "Baseline_Avg": True, "Spike_Tag": True},
            title="Timeline of Recorded Outlier Spike Events",
            template="plotly_dark",
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_outlier_time.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0f172a",
            font_color="#f1f5f9",
            height=360,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        st.plotly_chart(fig_outlier_time, use_container_width=True)

        # Micro-Inspector
        st.markdown("#### 🔬 Inspect Individual Outlier Trajectory vs Baseline")
        spike_titles = sorted(outliers_df["Article Title"].unique().tolist())
        inspected_title = st.selectbox("Select Spiked Article to View Trajectory:", options=spike_titles, key="tab_outliers_select")

        article_daily_df = df_daily_clean[df_daily_clean["Article Title"] == inspected_title].sort_values("Date")
        if not article_daily_df.empty:
            fig_inspect = px.line(
                article_daily_df,
                x="Date",
                y="Views",
                markers=True,
                title=f"Daily Traffic Curve for: {inspected_title}",
                template="plotly_dark",
                color_discrete_sequence=["#38bdf8"]
            )
            avg_val = article_daily_df["Views"].mean()
            fig_inspect.add_hline(
                y=avg_val,
                line_dash="dot",
                line_color="#f59e0b",
                annotation_text=f"Baseline Avg: {avg_val:.1f} views/day",
                annotation_position="bottom right"
            )
            fig_inspect.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#0f172a",
                font_color="#f1f5f9",
                height=320,
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_inspect, use_container_width=True)

        # Incident Registry Table & CSV Export
        st.markdown("#### 📋 Recorded Outlier Incident Registry")
        disp_outliers = outliers_df.rename(columns={
            "Article Title": "Article",
            "Spike_Views": "Spike Views",
            "Baseline_Avg": "Baseline Avg",
            "Surge_Multiplier": "Surge Factor",
            "Z_Score": "Z-Score",
            "Spike_Tag": "Anomaly Tag"
        })
        st.dataframe(
            disp_outliers[["Date", "Article", "Category", "Spike Views", "Baseline Avg", "Surge Factor", "Anomaly Tag"]],
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            label="📥 Export Outlier Incident Log (CSV)",
            data=outliers_df.to_csv(index=False).encode("utf-8"),
            file_name="blog_outlier_incident_log.csv",
            mime="text/csv",
            key="tab_outliers_download_csv"
        )
    else:
        st.success("No statistical outliers detected under current thresholds.")