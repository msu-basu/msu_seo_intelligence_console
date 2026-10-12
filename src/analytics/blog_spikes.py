"""
blog_spikes.py
High-performance analytics module for Day-Wise, Month-Wise blog performance,
Top Performer detection, and Outlier/Spike anomaly detection.
Features Streamlit in-memory caching (@st.cache_data) for sub-second chart rendering.
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import streamlit as st


def clean_article_title(path: str) -> str:
    """Extract clean readable title from blog URL path."""
    u = re.sub(r"^https?://[^/]+", "", str(path).strip(), flags=re.IGNORECASE)
    u = u.split("?")[0].split("#")[0]
    clean = re.sub(r"^/blog/|^/course/|^/|/$", "", u, flags=re.IGNORECASE)
    return clean.replace("-", " ").replace("_", " ").title() or "Unknown Blog"


def categorize_article(path: str) -> str:
    """Assign vertical category based on path keywords."""
    p = str(path).lower()
    if any(kw in p for kw in ["career", "jobs", "salary", "scope", "placement"]):
        return "Career & Placement Guides"
    if any(kw in p for kw in ["result", "exam", "cbse", "12th", "10th", "cutoff"]):
        return "Exams & Results"
    if any(kw in p for kw in ["skills", "courses", "learn", "how-to", "paramedical"]):
        return "Skills & Course Guides"
    return "General Campus News"


@st.cache_data(ttl=3600, show_spinner=False)
def prepare_clean_daily_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Clean raw GA4 blog data for day-wise and month-wise analytics. Cached in RAM."""
    if df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Detect page path column
    path_col = next(
        (c for c in df.columns if c in [
            "Page path and screen class", "Page path", "Top pages",
            "Page", "Landing page", "Full page URL"
        ]), df.columns[0]
    )

    # Exclude system/category pages
    bad_exact = {"/blog", "/blog/", "/", "(not set)", "", "/home", "/index", "/404"}
    df = df[~df[path_col].isin(bad_exact)].copy()
    filter_regex = re.compile(
        r"(?:admin|edit|\.jpg|\.png|\.gif|\.pdf|\.css|\.js|\.xml|\.txt|/tag/|/category/|/page/\d|/author/)",
        re.IGNORECASE
    )
    df = df[~df[path_col].str.contains(filter_regex, na=False)].copy()

    # Numeric clean
    for col in ["Views", "Active users", "Event count", "Key events"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False).str.strip(),
                errors="coerce"
            ).fillna(0)

    # Date parsing
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    else:
        df["Date"] = pd.NaT

    df = df.dropna(subset=["Date"]).copy()
    df["Page Path"] = df[path_col]
    df["Article Title"] = df["Page Path"].apply(clean_article_title)
    df["Category"] = df["Page Path"].apply(categorize_article)

    return df


@st.cache_data(ttl=3600, show_spinner=False)
def get_day_wise_performance(
    df: pd.DataFrame,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
    selected_blogs_tuple: Optional[Tuple[str, ...]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute day-wise total and per-blog performance within a date range.
    Returns: (total_daily_df, per_blog_daily_df) - Sub-50ms cached execution.
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    fdf = df.copy()
    if start_date is not None:
        fdf = fdf[fdf["Date"] >= pd.to_datetime(start_date)]
    if end_date is not None:
        fdf = fdf[fdf["Date"] <= pd.to_datetime(end_date)]

    # 1. Total Daily
    total_daily = (
        fdf.groupby("Date")
        .agg(
            Views=("Views", "sum"),
            Active_Users=("Active users", "max"),
            Active_Articles=("Page Path", "nunique")
        )
        .reset_index()
        .sort_values("Date")
    )
    total_daily["Rolling_7d_Views"] = total_daily["Views"].rolling(7, min_periods=1).mean().round(1)

    # 2. Per-blog daily (if blogs selected, or top 5 by default)
    if selected_blogs_tuple and len(selected_blogs_tuple) > 0:
        fdf_selected = fdf[fdf["Article Title"].isin(selected_blogs_tuple)].copy()
    else:
        top_titles = fdf.groupby("Article Title")["Views"].sum().nlargest(5).index.tolist()
        fdf_selected = fdf[fdf["Article Title"].isin(top_titles)].copy()

    per_blog_daily = (
        fdf_selected.groupby(["Date", "Article Title", "Category"])["Views"]
        .sum()
        .reset_index()
        .sort_values("Date")
    )

    return total_daily, per_blog_daily


@st.cache_data(ttl=3600, show_spinner=False)
def get_month_wise_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly aggregated performance with MoM growth rates. Cached in RAM."""
    if df.empty:
        return pd.DataFrame()

    mdf = df.copy()
    mdf["YearMonth"] = mdf["Date"].dt.to_period("M").astype(str)

    monthly = (
        mdf.groupby("YearMonth")
        .agg(
            Views=("Views", "sum"),
            Active_Users=("Active users", "max"),
            Articles_Active=("Page Path", "nunique"),
            Days=("Date", "nunique")
        )
        .reset_index()
        .sort_values("YearMonth")
    )
    monthly["Avg_Daily_Views"] = (monthly["Views"] / monthly["Days"]).round(1)
    monthly["MoM_Growth_%"] = (monthly["Views"].pct_change() * 100).round(1)

    return monthly


@st.cache_data(ttl=3600, show_spinner=False)
def get_top_performing_blogs(
    df: pd.DataFrame,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
    top_n: int = 10
) -> Dict[str, pd.DataFrame]:
    """Rank blogs within selected date window across multiple dimensions. Cached."""
    if df.empty:
        return {}

    fdf = df.copy()
    if start_date is not None:
        fdf = fdf[fdf["Date"] >= pd.to_datetime(start_date)]
    if end_date is not None:
        fdf = fdf[fdf["Date"] <= pd.to_datetime(end_date)]

    # Aggregated metrics per blog in period
    agg = (
        fdf.groupby(["Article Title", "Page Path", "Category"])
        .agg(
            Views=("Views", "sum"),
            Peak_Single_Day_Views=("Views", "max"),
            Avg_Daily_Views=("Views", "mean"),
            Active_Days=("Date", "nunique")
        )
        .reset_index()
    )
    agg["Est_Sessions"] = (agg["Views"] / 1.18).round().astype(int)
    agg["Avg_Daily_Views"] = agg["Avg_Daily_Views"].round(1)

    # 1. Volume leaders
    volume_leaders = agg.sort_values("Views", ascending=False).head(top_n).copy()

    # 2. Category leaders (best blog per category)
    category_leaders = (
        agg.sort_values(["Category", "Views"], ascending=[True, False])
        .groupby("Category")
        .first()
        .reset_index()
    )

    # 3. Peak surge leaders (highest single-day impact)
    surge_leaders = agg.sort_values("Peak_Single_Day_Views", ascending=False).head(top_n).copy()

    return {
        "volume_leaders": volume_leaders,
        "category_leaders": category_leaders,
        "surge_leaders": surge_leaders
    }


@st.cache_data(ttl=3600, show_spinner=False)
def detect_blog_outliers(
    df: pd.DataFrame,
    min_views: int = 20,
    z_threshold: float = 3.0,
    ratio_threshold: float = 2.5
) -> pd.DataFrame:
    """
    Detect statistical outliers / viral spikes per blog. Cached in RAM.
    """
    if df.empty:
        return pd.DataFrame()

    # Daily views per blog
    page_day = (
        df.groupby(["Page Path", "Article Title", "Category", "Date"])["Views"]
        .sum()
        .reset_index()
    )

    # Baseline statistics per article
    stats = (
        page_day.groupby("Page Path")["Views"]
        .agg(Mean_Views="mean", Std_Views="std", Total_Views="sum")
        .reset_index()
    )
    stats["Std_Views"] = stats["Std_Views"].fillna(0)

    merged = pd.merge(page_day, stats, on="Page Path")
    denom_std = merged["Std_Views"].replace(0, np.nan)
    merged["Z_Score"] = ((merged["Views"] - merged["Mean_Views"]) / denom_std).fillna(0).round(2)
    merged["Surge_Ratio"] = (merged["Views"] / merged["Mean_Views"].replace(0, np.nan)).fillna(0).round(2)

    # Filter outlier condition
    outliers = merged[
        (merged["Views"] >= min_views) &
        ((merged["Z_Score"] >= z_threshold) | (merged["Surge_Ratio"] >= ratio_threshold))
    ].copy()

    outliers = outliers.sort_values(["Views", "Surge_Ratio"], ascending=[False, False])
    outliers["Surge_Multiplier"] = outliers["Surge_Ratio"].apply(lambda r: f"{r:.1f}x Normal")
    outliers["Baseline_Avg"] = outliers["Mean_Views"].round(1)
    outliers["Spike_Views"] = outliers["Views"].astype(int)

    # Tag outlier type
    def _tag(row):
        cat = str(row["Category"]).lower()
        if "exam" in cat:
            return "Seasonal Exam / Result Spike"
        if row["Surge_Ratio"] >= 5.0:
            return "Viral Search / Media Surge"
        return "High Demand Surge"

    outliers["Spike_Tag"] = outliers.apply(_tag, axis=1)

    result_cols = [
        "Date", "Article Title", "Category", "Spike_Views",
        "Baseline_Avg", "Surge_Multiplier", "Z_Score", "Spike_Tag", "Page Path"
    ]
    return outliers[result_cols].reset_index(drop=True)