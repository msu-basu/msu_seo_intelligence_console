"""
Unit tests for blog_spikes module (Day-wise, Month-wise, Top Performers, Outlier Detection)
"""
import pandas as pd
import numpy as np
from src.analytics.blog_spikes import (
    clean_article_title,
    categorize_article,
    prepare_clean_daily_df,
    get_day_wise_performance,
    get_month_wise_performance,
    get_top_performing_blogs,
    detect_blog_outliers
)


def test_clean_article_title():
    assert clean_article_title("/blog/top-in-demand-skills-in-2026") == "Top In Demand Skills In 2026"
    assert clean_article_title("https://msu.edu.in/blog/career-in-optometry/") == "Career In Optometry"


def test_categorize_article():
    assert categorize_article("/blog/career-options-after-12th") == "Career & Placement Guides"
    assert categorize_article("/blog/cbse-10th-result-cutoff") == "Exams & Results"
    assert categorize_article("/blog/paramedical-courses-skills") == "Skills & Course Guides"
    assert categorize_article("/blog/campus-annual-fest") == "General Campus News"


def test_prepare_clean_daily_df():
    data = {
        "Page path and screen class": ["/blog", "/blog/test-article", "/blog/test-article"],
        "Views": ["10", "50", "30"],
        "Active users": ["5", "20", "15"],
        "Date": ["2026-09-01", "2026-09-01", "2026-09-02"]
    }
    df = pd.DataFrame(data)
    cleaned = prepare_clean_daily_df(df)
    # /blog should be filtered out
    assert len(cleaned) == 2
    assert "Article Title" in cleaned.columns
    assert "Category" in cleaned.columns
    assert cleaned["Views"].sum() == 80


def test_day_and_month_performance():
    data = {
        "Page path and screen class": ["/blog/art-1", "/blog/art-1", "/blog/art-2"],
        "Views": [100, 200, 50],
        "Active users": [10, 20, 5],
        "Date": ["2026-08-01", "2026-08-02", "2026-09-01"]
    }
    df = prepare_clean_daily_df(pd.DataFrame(data))
    
    t_daily, p_daily = get_day_wise_performance(df)
    assert len(t_daily) == 3
    assert t_daily["Views"].sum() == 350
    
    monthly = get_month_wise_performance(df)
    assert len(monthly) == 2
    assert "MoM_Growth_%" in monthly.columns


def test_detect_blog_outliers():
    # Create article with 10 normal days (mean ~5) and 1 extreme spike (100)
    dates = pd.date_range("2026-09-01", periods=11)
    views = [5, 6, 4, 5, 5, 6, 5, 4, 5, 6, 100]
    data = {
        "Page path and screen class": ["/blog/viral-post"] * 11,
        "Views": views,
        "Active users": [2] * 11,
        "Date": dates
    }
    df = prepare_clean_daily_df(pd.DataFrame(data))
    outliers = detect_blog_outliers(df, min_views=20, z_threshold=2.0, ratio_threshold=2.0)
    assert len(outliers) == 1
    assert outliers.iloc[0]["Spike_Views"] == 100
    assert "Normal" in outliers.iloc[0]["Surge_Multiplier"]