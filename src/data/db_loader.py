"""
db_loader.py
Direct PostgreSQL Database Loader for the MSU SEO Intelligence Console.
Loads data directly from PostgreSQL raw.* tables into pandas DataFrames,
matching the exact schema, columns, and data types expected by all dashboard pages.
Provides @st.cache_data for instant in-memory rendering with zero disk file dependencies.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Any
import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

from src.utils.logging import get_logger

logger = get_logger("db_loader")

# Load environment configuration
env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "web_analytics")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123")

# Map database tables to expected dashboard dataset keys and column names
TABLE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "overall": {
        "table": "raw.ga4_overall_baseline",
        "columns": {
            "session_source_medium": "Session source / medium",
            "sessions": "Sessions",
            "engaged_sessions": "Engaged sessions",
            "engagement_rate": "Engagement rate",
            "avg_engagement_time_per_session": "Average engagement time per session",
            "events_per_session": "Events per session",
            "event_count": "Event count",
            "key_events": "Key events",
            "session_key_event_rate": "Session key event rate",
            "total_revenue": "Total revenue",
        },
    },
    "blog": {
        "table": "raw.ga4_blog_daily",
        "columns": {
            "page_path": "Page path and screen class",
            "views": "Views",
            "bounce_rate": "Bounce rate",
            "active_users": "Active users",
            "views_per_active_user": "Views per active user",
            "avg_engagement_time_per_active_user": "Average engagement time per active user",
            "event_count": "Event count",
            "key_events": "Key events",
            "total_revenue": "Total revenue",
            "report_date": "Date",
        },
    },
    "course": {
        "table": "raw.ga4_course_daily",
        "columns": {
            "page_path": "Page path and screen class",
            "views": "Views",
            "bounce_rate": "Bounce rate",
            "active_users": "Active users",
            "views_per_active_user": "Views per active user",
            "avg_engagement_time_per_active_user": "Average engagement time per active user",
            "event_count": "Event count",
            "key_events": "Key events",
            "total_revenue": "Total revenue",
            "report_date": "Date",
        },
    },
    "course_performance": {
        "table": "raw.ga4_course_performance",
        "columns": {
            "landing_page": "Landing page + query string",
            "sessions": "Sessions",
            "event_count": "Event count",
            "engagement_rate": "Engagement rate",
        },
    },
    "device": {
        "table": "raw.ga4_device",
        "columns": {
            "device_category": "Device category",
            "active_users": "Active users",
            "new_users": "New users",
            "engaged_sessions": "Engaged sessions",
            "engagement_rate": "Engagement rate",
            "engaged_sessions_per_active_user": "Engaged sessions per active user",
            "avg_engagement_time_per_active_user": "Average engagement time per active user",
            "event_count": "Event count",
            "key_events": "Key events",
            "total_revenue": "Total revenue",
        },
    },
    "events": {
        "table": "raw.ga4_events",
        "columns": {
            "event_name": "Event name",
            "event_count": "Event count",
            "total_users": "Total users",
            "event_count_per_active_user": "Event count per active user",
            "total_revenue": "Total revenue",
        },
    },
    "geo_global": {
        "table": "raw.ga4_geo_global",
        "columns": {
            "country": "Country",
            "city": "City",
            "active_users": "Active users",
            "new_users": "New users",
            "engaged_sessions": "Engaged sessions",
            "engagement_rate": "Engagement rate",
            "engaged_sessions_per_active_user": "Engaged sessions per active user",
            "avg_engagement_time_per_active_user": "Average engagement time per active user",
            "event_count": "Event count",
            "key_events": "Key events",
            "user_key_event_rate": "User key event rate",
            "total_revenue": "Total revenue",
        },
    },
    "geo_pagepath": {
        "table": "raw.ga4_geo_city_device",
        "columns": {
            "city": "City",
            "mobile_active_users": "Mobile",
            "desktop_active_users": "Desktop",
            "tablet_active_users": "Tablet",
            "total_active_users": "Total Users",
        },
    },
    "blog_gsc_pages": {
        "table": "raw.gsc_blog_pages",
        "columns": {
            "page_url": "Top pages",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "ctr": "CTR",
            "position": "Position",
        },
    },
    "blog_gsc_queries": {
        "table": "raw.gsc_blog_queries",
        "columns": {
            "query": "Top queries",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "ctr": "CTR",
            "position": "Position",
        },
    },
    "blog_gsc_countries": {
        "table": "raw.gsc_blog_countries",
        "columns": {
            "country": "Country",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "ctr": "CTR",
            "position": "Position",
        },
    },
    "blog_gsc_devices": {
        "table": "raw.gsc_blog_devices",
        "columns": {
            "device": "Device",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "ctr": "CTR",
            "position": "Position",
        },
    },
    "course_gsc_pages": {
        "table": "raw.gsc_course_pages",
        "columns": {
            "page_url": "Top pages",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "ctr": "CTR",
            "position": "Position",
        },
    },
    "course_gsc_queries": {
        "table": "raw.gsc_course_queries",
        "columns": {
            "query": "Top queries",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "ctr": "CTR",
            "position": "Position",
        },
    },
    "course_gsc_countries": {
        "table": "raw.gsc_course_countries",
        "columns": {
            "country": "Country",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "ctr": "CTR",
            "position": "Position",
        },
    },
    "course_gsc_devices": {
        "table": "raw.gsc_course_devices",
        "columns": {
            "device": "Device",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "ctr": "CTR",
            "position": "Position",
        },
    },
}

# Mapping from filename aliases to dataset keys
FILE_TO_KEY_MAP = {
    "00_Overall_GA4_Baseline.parquet": "overall",
    "00_overall.csv": "overall",
    "01_Blog_GA4.parquet": "blog",
    "01_blog.csv": "blog",
    "blog_ga4.parquet": "blog",
    "02_Course_GA4.parquet": "course",
    "02_course.csv": "course",
    "03_Course_Performance.parquet": "course_performance",
    "04_Device_GA4.parquet": "device",
    "05_Events_GA4.parquet": "events",
    "06_Geo_Global_GA4.parquet": "geo_global",
    "06_Geo_PagePath_GA4.parquet": "geo_pagepath",
    "gsc_blog_pages.parquet": "blog_gsc_pages",
    "gsc_blog_queries.parquet": "blog_gsc_queries",
    "gsc_blog_countries.parquet": "blog_gsc_countries",
    "gsc_blog_devices.parquet": "blog_gsc_devices",
    "gsc_course_pages.parquet": "course_gsc_pages",
    "gsc_course_queries.parquet": "course_gsc_queries",
    "gsc_course_countries.parquet": "course_gsc_countries",
    "gsc_course_devices.parquet": "course_gsc_devices",
}


def get_db_connection():
    """Establishes connection to PostgreSQL database."""
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=3,
    )


def test_db_connection() -> bool:
    """Tests if PostgreSQL is reachable."""
    try:
        conn = get_db_connection()
        conn.close()
        return True
    except Exception:
        return False


def load_dataset_from_db(dataset_key: str) -> pd.DataFrame:
    """
    Loads a single dataset directly from PostgreSQL raw.* tables.
    Returns DataFrame matching expected column names and types.
    """
    schema_info = TABLE_SCHEMAS.get(dataset_key)
    if not schema_info:
        logger.warning("No database mapping for dataset key: %s", dataset_key)
        return pd.DataFrame()

    table_name = schema_info["table"]
    col_map = schema_info["columns"]
    select_cols = ", ".join(col_map.keys())

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(f"SELECT {select_cols} FROM {table_name};")
            rows = cur.fetchall()
        conn.close()

        df = pd.DataFrame(rows, columns=list(col_map.values()))
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        df.attrs["source_file"] = f"postgresql://{table_name}"
        df.attrs["dataset_type"] = dataset_key
        return df
    except Exception as e:
        logger.error("Failed to load '%s' from %s: %s", dataset_key, table_name, e)
        return pd.DataFrame()


def load_all_from_db() -> Dict[str, pd.DataFrame]:
    """
    Loads all datasets directly from PostgreSQL.
    Merges GSC Pages into Blog and Course, and populates aliases.
    """
    from src.data.loaders import _merge_gsc_into_ga4

    datasets: Dict[str, pd.DataFrame] = {}
    if not test_db_connection():
        logger.warning("PostgreSQL connection failed; unable to load from database.")
        return datasets

    for key in TABLE_SCHEMAS:
        df = load_dataset_from_db(key)
        if not df.empty:
            datasets[key] = df

    # Merge GSC into GA4 for Course and Blog
    if "course" in datasets and "course_gsc_pages" in datasets:
        datasets["course"] = _merge_gsc_into_ga4(datasets["course"], datasets["course_gsc_pages"])

    if "blog" in datasets and "blog_gsc_pages" in datasets:
        datasets["blog"] = _merge_gsc_into_ga4(datasets["blog"], datasets["blog_gsc_pages"])

    # Aliases
    alias_mappings = [
        ("gsc_blog_pages", "blog_gsc_pages"),
        ("blog_gsc_pages", "gsc_blog_pages"),
        ("gsc_blog_queries", "blog_gsc_queries"),
        ("blog_gsc_queries", "gsc_blog_queries"),
        ("gsc_queries", "course_gsc_queries"),
        ("course_gsc_queries", "gsc_queries"),
        ("gsc_course_pages", "course_gsc_pages"),
        ("course_gsc_pages", "gsc_course_pages"),
    ]
    for target_key, source_key in alias_mappings:
        if target_key not in datasets and source_key in datasets:
            datasets[target_key] = datasets[source_key]

    if "geo" not in datasets:
        if "geo_pagepath" in datasets:
            datasets["geo"] = datasets["geo_pagepath"]
        elif "geo_global" in datasets:
            datasets["geo"] = datasets["geo_global"]

    if "countries" not in datasets:
        if "course_gsc_countries" in datasets:
            datasets["countries"] = datasets["course_gsc_countries"]

    return datasets


def load_file_or_db(fname: str) -> pd.DataFrame:
    """
    Transparent loader for pages reading by filename.
    Checks PostgreSQL first; falls back to data/processed/<fname> if DB is unavailable.
    """
    base_name = Path(fname).name
    dataset_key = FILE_TO_KEY_MAP.get(base_name)

    # 1. Try Pure Database
    if dataset_key and test_db_connection():
        df = load_dataset_from_db(dataset_key)
        if not df.empty:
            return df

    # 2. Fallback to file on disk
    file_path = Path("data/processed") / base_name
    if file_path.exists():
        if file_path.suffix.lower() == ".parquet":
            return pd.read_parquet(file_path)
        elif file_path.suffix.lower() == ".csv":
            return pd.read_csv(file_path)

    return pd.DataFrame()
