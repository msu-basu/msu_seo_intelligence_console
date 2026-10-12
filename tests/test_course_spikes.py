"""
Unit tests for course_spikes module (Day-wise, Month-wise, Top Programs, Outlier Detection)
"""
import pandas as pd
import numpy as np
from src.analytics.course_spikes import (
    prepare_clean_daily_course_df,
    get_day_wise_course_performance,
    get_month_wise_course_performance,
    get_top_performing_courses,
    detect_course_outliers
)


def test_prepare_clean_daily_course_df():
    data = {
        "Page path and screen class": ["/course/btech-ai-ml", "/about-us", "/course/mba-finance"],
        "Views": ["25", "100", "50"],
        "Active users": ["10", "50", "20"],
        "Date": ["2026-09-01", "2026-09-01", "2026-09-02"]
    }
    df = pd.DataFrame(data)
    cleaned = prepare_clean_daily_course_df(df)
    # /about-us should be excluded
    assert len(cleaned) == 2
    assert "Course Title" in cleaned.columns
    assert "Degree Level" in cleaned.columns
    assert cleaned["Views"].sum() == 75


def test_course_day_and_month_performance():
    data = {
        "Page path and screen class": ["/course/btech-ai-ml", "/course/btech-ai-ml", "/course/mba-finance"],
        "Views": [100, 200, 50],
        "Active users": [10, 20, 5],
        "Date": ["2026-08-01", "2026-08-02", "2026-09-01"]
    }
    df = prepare_clean_daily_course_df(pd.DataFrame(data))
    
    t_daily, p_daily = get_day_wise_course_performance(df)
    assert len(t_daily) == 3
    assert t_daily["Views"].sum() == 350
    
    monthly = get_month_wise_course_performance(df)
    assert len(monthly) == 2
    assert "MoM_Growth_%" in monthly.columns


def test_detect_course_outliers():
    dates = pd.date_range("2026-09-01", periods=11)
    views = [4, 5, 5, 4, 5, 4, 5, 5, 4, 5, 80]
    data = {
        "Page path and screen class": ["/course/btech-surge"] * 11,
        "Views": views,
        "Active users": [2] * 11,
        "Date": dates
    }
    df = prepare_clean_daily_course_df(pd.DataFrame(data))
    outliers = detect_course_outliers(df, min_views=15, z_threshold=2.0, ratio_threshold=2.0)
    assert len(outliers) == 1
    assert outliers.iloc[0]["Spike_Views"] == 80
    assert "Normal" in outliers.iloc[0]["Surge_Multiplier"]