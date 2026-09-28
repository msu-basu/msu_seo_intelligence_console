import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

st.title("📅 Daily Traffic Trends")
st.caption("Day-by-day views from GA4 blog and course exports. Grain: 1 row = page × date.")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family:"Inter",sans-serif; }
div[data-testid="metric-container"] {
    background:linear-gradient(135deg,#1e293b,#0f172a);
    border:1px solid #334155; border-radius:12px; padding:16px 20px;
}
div[data-testid="metric-container"] label { color:#94a3b8!important; font-size:11px!important; text-transform:uppercase; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#f1f5f9!important; font-size:24px!important; font-weight:700!important; }
</style>""", unsafe_allow_html=True)

DATA_DIR = Path("data/input")

@st.cache_data
def load_daily(fname):
    p = DATA_DIR / fname
    if not p.exists(): return pd.DataFrame()
    df = pd.read_csv(p, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    if "Views" in df.columns:
        df["Views"] = pd.to_numeric(df["Views"].astype(str).str.replace(",","",regex=False),errors="coerce").fillna(0)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df

blog_raw   = load_daily("01_Blog_GA4.csv")
course_raw = load_daily("02_Course_GA4.csv")

if blog_raw.empty and course_raw.empty:
    st.error("No GA4 data found in `data/input/`.")
    st.stop()

# ── Daily aggregates ──────────────────────────────────────────────────────────
frames = []
if not blog_raw.empty and "Date" in blog_raw.columns:
    bd = blog_raw.groupby("Date")["Views"].sum().reset_index(); bd["Channel"] = "Blog"
    frames.append(bd)
if not course_raw.empty and "Date" in course_raw.columns:
    cd = course_raw.groupby("Date")["Views"].sum().reset_index(); cd["Channel"] = "Courses"
    frames.append(cd)

daily = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# ── Date range filter ─────────────────────────────────────────────────────────
if not daily.empty:
    min_d = daily["Date"].min().date()
    max_d = daily["Date"].max().date()
    d1, d2 = st.sidebar.date_input("Date Range", value=[min_d, max_d],
                                    min_value=min_d, max_value=max_d)
    daily = daily[(daily["Date"].dt.date >= d1) & (daily["Date"].dt.date <= d2)]

# ── KPIs ──────────────────────────────────────────────────────────────────────
b_tot = int(daily[daily["Channel"]=="Blog"]["Views"].sum()) if not daily.empty else 0
c_tot = int(daily[daily["Channel"]=="Courses"]["Views"].sum()) if not daily.empty else 0
b_avg = int(daily[daily["Channel"]=="Blog"]["Views"].mean()) if not daily.empty else 0
c_avg = int(daily[daily["Channel"]=="Courses"]["Views"].mean()) if not daily.empty else 0

k1,k2,k3,k4 = st.columns(4)
k1.metric("Blog Views (Period)", f"{b_tot:,}")
k2.metric("Course Views (Period)", f"{c_tot:,}")
k3.metric("Avg Daily Blog Views", f"{b_avg:,}")
k4.metric("Avg Daily Course Views", f"{c_avg:,}")

st.markdown("---")

# ── Combined Line Chart ───────────────────────────────────────────────────────
st.markdown("### Daily Views Trend — Blog vs Courses")
if not daily.empty:
    fig = px.line(daily, x="Date", y="Views", color="Channel",
                  color_discrete_map={"Blog":"#38bdf8","Courses":"#a78bfa"},
                  template="plotly_dark",
                  labels={"Views":"Daily Views","Date":""})
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                      font_color="#f1f5f9", hovermode="x unified", height=420,
                      xaxis=dict(gridcolor="#1e293b"), yaxis=dict(gridcolor="#1e293b"),
                      legend=dict(orientation="h",y=1.02), margin=dict(l=20,r=20,t=20,b=20))
    st.plotly_chart(fig, width="stretch")

st.markdown("---")

# ── 7-Day Rolling Average ──────────────────────────────────────────────────────
st.markdown("### 7-Day Rolling Average Views")
if not daily.empty:
    roll = daily.copy()
    roll = roll.sort_values("Date")
    roll["Rolling 7d"] = roll.groupby("Channel")["Views"].transform(lambda x: x.rolling(7,min_periods=1).mean())
    fig2 = px.line(roll, x="Date", y="Rolling 7d", color="Channel",
                   color_discrete_map={"Blog":"#38bdf8","Courses":"#a78bfa"},
                   template="plotly_dark",
                   labels={"Rolling 7d":"7-Day Avg Views"})
    fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f172a",
                       font_color="#f1f5f9", hovermode="x unified", height=380,
                       xaxis=dict(gridcolor="#1e293b"), yaxis=dict(gridcolor="#1e293b"),
                       margin=dict(l=20,r=20,t=20,b=20))
    st.plotly_chart(fig2, width="stretch")

st.markdown("---")

# ── Top Days ────────────────────────────────────────────────────────────────────
st.markdown("### Highest Traffic Days")
if not daily.empty:
    pivot = daily.pivot_table(index="Date", columns="Channel", values="Views", aggfunc="sum").fillna(0)
    pivot["Total"] = pivot.sum(axis=1)
    top_days = pivot.sort_values("Total", ascending=False).head(15).reset_index()
    top_days["Date"] = top_days["Date"].dt.strftime("%Y-%m-%d")
    st.dataframe(top_days, hide_index=True, width="stretch")
