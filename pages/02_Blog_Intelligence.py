"""
02_Blog_Intelligence.py  — FIXED VERSION
-----------------------------------------
ROOT CAUSE (previous version):
  GA4 blog CSV is daily-grain (1 row per page per date, 365 rows/page).
  Active users is a PERIOD-LEVEL CONSTANT — same value every day per page.
  Old code summed it 365x, inflating every metric.

FIX:
  1. Load raw 195,640 rows.
  2. GROUP BY page_path FIRST:
       Views, Event count, Key events  -> SUM  (daily counters)
       Active users                    -> MAX  (period constant)
  3. Derive Sessions = SUM(Views) / 1.18
  4. JOIN GSC only AFTER aggregation.
  5. Calculate ratios on grain-correct frame.
"""

from __future__ import annotations
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =============================================================================
# PAGE CONFIG
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
    margin: 24px 0 12px 0;
}
.grain-note {
    background: #0f2a1d; border: 1px solid #16a34a; border-radius: 8px;
    padding: 10px 16px; font-size: 13px; color: #86efac; margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CONSTANTS
# =============================================================================
DATA_DIR = Path("data/input")

FILTER_EXACT = {"/blog", "/blog/", "/", "(not set)", "", "/home", "/index", "/404"}
FILTER_REGEX = re.compile(
    r"(admin|edit|\.jpg|\.png|\.gif|\.pdf|\.css|\.js|\.xml|\.txt"
    r"|/tag/|/category/|/page/\d|/author/)", re.IGNORECASE
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
# LOADERS
# =============================================================================
@st.cache_data(show_spinner="Loading GA4 blog daily data...")
def load_raw_blog() -> pd.DataFrame:
    for p in [DATA_DIR/"01_Blog_GA4.csv", DATA_DIR/"blog_ga4.csv"]:
        if p.exists():
            df = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
            df.columns = [c.strip() for c in df.columns]
            return df
    return pd.DataFrame()

@st.cache_data(show_spinner="Loading GSC pages...")
def load_gsc_pages() -> pd.DataFrame:
    p = DATA_DIR/"gsc_blog_pages.csv"
    if p.exists():
        df = pd.read_csv(p, encoding="utf-8-sig")
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame()

@st.cache_data(show_spinner="Loading GSC queries...")
def load_gsc_queries() -> pd.DataFrame:
    p = DATA_DIR/"gsc_blog_queries.csv"
    if p.exists():
        df = pd.read_csv(p, encoding="utf-8-sig")
        df.columns = [c.strip() for c in df.columns]
        return df
    return pd.DataFrame()


# =============================================================================
# AGGREGATION PIPELINE — THE CORE FIX
# =============================================================================
@st.cache_data(show_spinner="Aggregating to page level...")
def build_page_df(df_raw: pd.DataFrame, df_gsc: pd.DataFrame) -> pd.DataFrame:
    if df_raw.empty:
        return pd.DataFrame()

    pc = next(
        (c for c in df_raw.columns if c in [
            "Page path and screen class","Page path","Top pages",
            "Page","Landing page","Full page URL"
        ]), df_raw.columns[0]
    )

    def fc(cands): return next((c for c in cands if c in df_raw.columns), None)
    vc = fc(["Views","Pageviews","Event count"])
    ac = fc(["Active users","Users"])
    ec = fc(["Event count"])
    kc = fc(["Key events","Conversions"])

    for col in [vc, ac, ec, kc]:
        if col and col in df_raw.columns:
            df_raw[col] = df_raw[col].apply(_pn)

    # AGGREGATE — SUM daily counters, MAX period constants
    agg = {}
    if vc: agg["Views"]        = (vc, "sum")   # daily counter -> SUM
    if ac: agg["Active Users"] = (ac, "max")   # period constant -> MAX (NOT SUM!)
    if ec: agg["Event Count"]  = (ec, "sum")
    if kc: agg["Key Events"]   = (kc, "sum")

    df = (
        df_raw.groupby(pc).agg(**agg)
        .reset_index().rename(columns={pc: "Page Path"})
    )

    # Filter non-article paths
    df = df[~df["Page Path"].isin(FILTER_EXACT)].copy()
    df = df[~df["Page Path"].str.contains(FILTER_REGEX, na=False)].copy()

    # Derive Sessions from total Views
    v = df.get("Views", pd.Series(0, index=df.index))
    df["Sessions"] = np.maximum((v / VIEWS_SESSION_RATIO).round().astype(int), 1)

    # CTA Clicks and Leads
    if "CTA Clicks" not in df.columns:
        df["CTA Clicks"] = (df["Sessions"] * CTA_CLICK_RATE).round().astype(int)
    if "Key Events" in df.columns:
        df["Leads"] = df["Key Events"].astype(int)
    else:
        df["Leads"] = (df["CTA Clicks"] * LEAD_RATE).round().astype(int)

    # Impressions
    if "Impressions" not in df.columns:
        df["Impressions"] = (v * IMPRESSION_RATE).round().astype(int)

    # JOIN GSC at aggregated grain
    if not df_gsc.empty:
        gpc = next(
            (c for c in df_gsc.columns if "page" in c.lower() or "url" in c.lower()), None
        )
        if gpc:
            g = df_gsc.copy()
            g["_norm"] = g[gpc].apply(_strip_domain)
            if "CTR" in g.columns:
                g["GSC CTR (%)"] = (
                    g["CTR"].astype(str).str.replace("%","",regex=False).str.strip()
                    .pipe(pd.to_numeric, errors="coerce").fillna(0.0)
                )
            for col in ["Clicks","Impressions","Position"]:
                if col in g.columns:
                    g[f"GSC {col}"] = (
                        g[col].astype(str).str.replace(",","",regex=False)
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
# LOAD
# =============================================================================
df_raw    = load_raw_blog()
df_gsc_pg = load_gsc_pages()
df_gsc_q  = load_gsc_queries()

if df_raw.empty:
    st.error("No blog dataset found in `data/input/`. Expected `01_Blog_GA4.csv`.")
    st.stop()

df = build_page_df(df_raw, df_gsc_pg)

if df.empty:
    st.error("No valid article rows found after filtering.")
    st.stop()

# =============================================================================
# HEADER
# =============================================================================
st.title("📝 Blog Intelligence & Conversion Console")

st.markdown(
    "<div class='grain-note'>DATA QUALITY: GA4 exports one row per page per date "
    "(365 rows/page). Active users is a period constant -- this dashboard uses "
    "MAX(Active users) + SUM(Views) for correct metrics.</div>",
    unsafe_allow_html=True,
)

# =============================================================================
# SIDEBAR
# =============================================================================
st.sidebar.header("Blog Filters")
cats = sorted(df["Category"].unique())
sel_cats = st.sidebar.multiselect("Content Category", options=cats, default=cats)
max_v = max(int(df["Views"].max()), 10)
min_v = st.sidebar.number_input("Minimum Article Views", 0, max_v, 0, step=50)

fdf = df[df["Category"].isin(sel_cats) & (df["Views"] >= min_v)].copy()

# =============================================================================
# KPIs
# =============================================================================
st.markdown("<div class='section-header'>Platform Scorecard</div>", unsafe_allow_html=True)

ta = fdf["Article Title"].nunique()
tv = int(fdf["Views"].sum())
ts = int(fdf["Sessions"].sum())
tc = int(fdf["CTA Clicks"].sum())
tl = int(fdf["Leads"].sum())
ac = (tc / ts * 100) if ts else 0.0
av = (tl / ts * 100) if ts else 0.0

k1,k2,k3,k4,k5,k6 = st.columns(6)
k1.metric("Total Articles",    f"{ta:,}")
k2.metric("Total Views",       f"{tv:,}")
k3.metric("Est. Sessions",     f"{ts:,}", help="Views / 1.18")
k4.metric("CTA Clicks",        f"{tc:,}", help="Sessions x 20%")
k5.metric("Avg CTA CTR",       f"{ac:.1f}%")
k6.metric("Leads / CVR",       f"{tl:,}  ({av:.1f}%)", help="CTA Clicks x 12%")

st.markdown("---")

# =============================================================================
# READERSHIP
# =============================================================================
st.markdown("<div class='section-header'>Readership Intelligence</div>", unsafe_allow_html=True)

cat_s = fdf.groupby("Category").agg(Views=("Views","sum"), Articles=("Article Title","nunique")).reset_index()
c1, c2 = st.columns([1,2])

with c1:
    fig_pie = px.pie(cat_s, values="Views", names="Category", hole=0.45,
                     title="Views by Category",
                     color_discrete_sequence=px.colors.qualitative.Bold)
    fig_pie.update_traces(textinfo="percent+label", pull=[0.03]*len(cat_s))
    fig_pie.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", font_color="#f1f5f9",
                          title_font_color="#38bdf8", height=360,
                          margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    t10 = fdf.nlargest(10, "Views")
    fig_bar = px.bar(t10, x="Views", y="Article Title", orientation="h",
                     color="Category", title="Top 10 Articles by Views",
                     color_discrete_sequence=px.colors.qualitative.Bold)
    fig_bar.update_layout(yaxis=dict(autorange="reversed"),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#f1f5f9", title_font_color="#38bdf8", height=360,
                          margin=dict(l=10,r=10,t=50,b=10),
                          legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# =============================================================================
# CATEGORY BENCHMARKS
# =============================================================================
st.markdown("<div class='section-header'>Category Benchmark Analysis</div>", unsafe_allow_html=True)

cb = (fdf.groupby("Category").agg(
    Articles=("Article Title","nunique"),
    Total_Views=("Views","sum"),
    Total_Leads=("Leads","sum"),
    Avg_CTR=("CTA CTR (%)","mean"),
    Avg_CVR=("Lead CVR (%)","mean"),
).reset_index().rename(columns={
    "Total_Views":"Total Views","Total_Leads":"Total Leads",
    "Avg_CTR":"Avg CTA CTR (%)","Avg_CVR":"Avg Lead CVR (%)",
}))

bm = cb.melt(id_vars="Category", value_vars=["Avg CTA CTR (%)","Avg Lead CVR (%)"],
             var_name="Metric", value_name="Value")
fig_b = px.bar(bm, x="Category", y="Value", color="Metric", barmode="group",
               title="Avg CTR vs CVR by Category",
               color_discrete_map={"Avg CTA CTR (%)":"#38bdf8","Avg Lead CVR (%)":"#a78bfa"})
fig_b.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#f1f5f9", title_font_color="#38bdf8", height=350,
                    margin=dict(l=10,r=10,t=50,b=10), legend=dict(orientation="h",y=-0.25))
st.plotly_chart(fig_b, use_container_width=True)
st.dataframe(cb.style.format({"Avg CTA CTR (%)":"{:.2f}%","Avg Lead CVR (%)":"{:.2f}%",
                               "Total Views":"{:,.0f}","Total Leads":"{:,.0f}"}),
             use_container_width=True, hide_index=True)

st.markdown("---")

# =============================================================================
# GSC KEYWORD INTELLIGENCE
# =============================================================================
st.markdown("<div class='section-header'>Search Keyword Intelligence (GSC)</div>", unsafe_allow_html=True)

if not df_gsc_q.empty:
    qc = next((c for c in df_gsc_q.columns if "quer" in c.lower() or "top" in c.lower()),
               df_gsc_q.columns[0])
    gq = df_gsc_q.copy()
    for col in ["Clicks","Impressions","Position"]:
        if col in gq.columns:
            gq[col] = (gq[col].astype(str).str.replace(",","",regex=False)
                       .pipe(pd.to_numeric, errors="coerce").fillna(0))
    if "CTR" in gq.columns:
        gq["CTR (%)"] = (gq["CTR"].astype(str).str.replace("%","",regex=False).str.strip()
                         .pipe(pd.to_numeric, errors="coerce").fillna(0))
    tq = (gq.rename(columns={qc:"Search Query"}).nlargest(15,"Clicks")
          [["Search Query","Clicks","Impressions","CTR (%)","Position"]])
    cq1, cq2 = st.columns([2,3])
    with cq1:
        st.markdown("**Top 15 Organic Queries by Clicks**")
        st.dataframe(tq.style.format({"Clicks":"{:,.0f}","Impressions":"{:,.0f}",
                                       "CTR (%)":"{:.2f}%","Position":"{:.1f}"}),
                     use_container_width=True, hide_index=True, height=430)
    with cq2:
        fkw = px.bar(tq, x="Clicks", y="Search Query", orientation="h",
                     color="Clicks", color_continuous_scale="Blues",
                     title="Top Organic Keywords by Clicks")
        fkw.update_layout(yaxis=dict(autorange="reversed"),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#f1f5f9", title_font_color="#38bdf8", height=430,
                          margin=dict(l=10,r=10,t=50,b=10), coloraxis_showscale=False)
        st.plotly_chart(fkw, use_container_width=True)
else:
    st.info("GSC queries file not found at `data/input/gsc_blog_queries.csv`.")

st.markdown("---")

# =============================================================================
# 4-QUADRANT MATRIX
# =============================================================================
st.markdown("<div class='section-header'>Strategic 4-Quadrant Optimization Matrix</div>",
            unsafe_allow_html=True)

ps = (fdf.groupby(["Article Title","Category"]).agg(
    Views=("Views","sum"), Sessions=("Sessions","sum"),
    CTA_Clicks=("CTA Clicks","sum"), Leads=("Leads","sum"),
    Impressions=("Impressions","sum"),
).reset_index().rename(columns={"CTA_Clicks":"CTA Clicks"}))

s2 = ps["Sessions"].replace(0, np.nan)
ps["CTA CTR (%)"]  = (ps["CTA Clicks"] / s2 * 100).fillna(0).round(2)
ps["Lead CVR (%)"] = (ps["Leads"] / s2 * 100).fillna(0).round(2)

vt = float(np.maximum(ps["Views"].median(), 1))
ct = float(ps["Lead CVR (%)"].median())

cmap = {"Superstars":"#16a34a","Hidden Gems":"#2563eb",
        "CRO Bottlenecks":"#d97706","Underperformers":"#dc2626"}

def _q(r):
    hv = r["Views"] >= vt; hc = r["Lead CVR (%)"] >= ct
    if hv and hc:  return "Superstars"
    if not hv and hc: return "Hidden Gems"
    if hv and not hc: return "CRO Bottlenecks"
    return "Underperformers"

ps["Quadrant"] = ps.apply(_q, axis=1)
ps["Views_P"]  = np.maximum(1, ps["Views"])

fm = px.scatter(ps, x="Views_P", y="Lead CVR (%)", size=np.maximum(ps["Leads"],1),
                color="Quadrant", color_discrete_map=cmap, hover_name="Article Title",
                hover_data={"Category":True,"Views":True,"Sessions":True,
                            "CTA Clicks":True,"CTA CTR (%)":True,"Leads":True,"Views_P":False},
                log_x=True, title="Blog Portfolio Matrix (Median Views & CVR Thresholds)",
                labels={"Lead CVR (%)":"Lead CVR (%)","Views_P":"Total Views (Log Scale)"})
fm.add_vline(x=vt, line_dash="dash", line_color="#64748b",
             annotation_text=f"Median Views ({int(vt):,})",
             annotation_position="top left", annotation_font_color="#94a3b8")
fm.add_hline(y=ct, line_dash="dash", line_color="#64748b",
             annotation_text=f"Median CVR ({ct:.2f}%)",
             annotation_position="bottom right", annotation_font_color="#94a3b8")
fm.update_layout(height=520, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                 font_color="#f1f5f9", title_font_color="#38bdf8",
                 legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
                 margin=dict(l=20,r=20,t=70,b=20),
                 xaxis=dict(gridcolor="#1e293b"), yaxis=dict(gridcolor="#1e293b"))
st.plotly_chart(fm, use_container_width=True)

qss = ps[ps["Quadrant"]=="Superstars"]
qhg = ps[ps["Quadrant"]=="Hidden Gems"]
qcb = ps[ps["Quadrant"]=="CRO Bottlenecks"]
qup = ps[ps["Quadrant"]=="Underperformers"]

qc1,qc2,qc3,qc4 = st.columns(4)
qc1.metric("Superstars",     f"{len(qss)} Articles", f"{int(qss['Leads'].sum()):,} Leads")
qc2.metric("Hidden Gems",    f"{len(qhg)} Articles", "Needs Promotion")
qc3.metric("CRO Bottlenecks",f"{len(qcb)} Articles", "Fix CTAs Urgently")
qc4.metric("Underperformers",f"{len(qup)} Articles", "Revamp / Merge")

COLS = ["Article Title","Category","Views","Sessions","CTA CTR (%)","Lead CVR (%)","Leads"]
t1,t2,t3,t4 = st.tabs(["CRO Bottlenecks","Hidden Gems","Superstars","Underperformers"])
with t1:
    st.warning("High readership but poor lead capture. Redesign CTAs, add embedded lead forms, improve mobile UX.")
    st.dataframe(qcb[COLS].sort_values("Views",ascending=False), use_container_width=True, hide_index=True)
with t2:
    st.info("Strong conversion intent -- needs more traffic. Feature on homepage, add internal links, newsletters.")
    st.dataframe(qhg[COLS].sort_values("Lead CVR (%)",ascending=False), use_container_width=True, hide_index=True)
with t3:
    st.success("Core lead drivers -- protect rankings! Keep content fresh, verify CTAs, monitor search position.")
    st.dataframe(qss[COLS].sort_values("Leads",ascending=False), use_container_width=True, hide_index=True)
with t4:
    st.error("Low traffic and low conversion. Refresh keywords, consolidate similar articles, or prune/redirect.")
    st.dataframe(qup[COLS].sort_values("Views",ascending=True), use_container_width=True, hide_index=True)

st.markdown("---")

# =============================================================================
# ARTICLE DIRECTORY
# =============================================================================
st.markdown("<div class='section-header'>Full Article Directory</div>", unsafe_allow_html=True)

srch = st.text_input("Search articles by title or category:")
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

