"""Robust CSV loading and dataset detection for the MSU SEO console."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Dict, Iterable, Union
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from src.utils.logging import get_logger

logger = get_logger("loaders")

ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "cp1252",
    "latin1",
)

CUSTOM_NA_VALUES = (
    "(not set)",
    "not set",
    "(not provided)",
    "n/a",
    "N/A",
    "null",
    "NULL",
    "-",
)

# Exact/strong filename rules take precedence over generic column signatures.
FILENAME_DATASET_RULES = (
    ("00_overall", "overall"),
    ("01_blog", "blog"),
    ("02_course_ga4", "course"),
    ("02_course", "course"),
    ("03_course_performance", "course_performance"),
    ("04_device", "device"),
    ("05_events", "events"),
    ("06_geo_global", "geo_global"),
    ("06_geo_pagepath", "geo_pagepath"),
    # GSC Course Files
    ("gsc_course_pages", "course_gsc_pages"),
    ("gsc_course_queries", "course_gsc_queries"),
    ("gsc_course_devices", "course_gsc_devices"),
    ("gsc_course_countries", "course_gsc_countries"),
    # GSC Blog Files
    ("gsc_blog_pages", "blog_gsc_pages"),
    ("gsc_blog_queries", "blog_gsc_queries"),
    ("gsc_blog_devices", "blog_gsc_devices"),
    ("gsc_blog_countries", "blog_gsc_countries"),
)


def clean_url_to_path(url_val: object) -> str:
    """Convert full GSC URLs to lowercase relative pagePath for 100% merge accuracy."""
    if not isinstance(url_val, str) or not url_val.strip():
        return ""
    url_str = url_val.strip().lower()
    if url_str.startswith("http"):
        path = urlparse(url_str).path
    else:
        path = url_str
    path = path.rstrip("/")
    return path if path else "/"


def _decode_bytes(raw: bytes) -> str:
    """Decode bytes using BOM-aware and null-byte-aware encoding detection."""
    if not raw:
        return ""

    if raw.startswith(b"\xef\xbb\xbf"):
        ordered = ("utf-8-sig", "utf-8", "cp1252", "latin1")
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        ordered = ("utf-16", "utf-16-le", "utf-16-be")
    else:
        nul_ratio = raw.count(b"\x00") / max(len(raw), 1)
        if nul_ratio > 0.15:
            ordered = (
                "utf-16-le",
                "utf-16-be",
                "utf-8-sig",
                "utf-8",
                "cp1252",
                "latin1",
            )
        else:
            ordered = ENCODINGS

    best_text = ""
    best_score = -1

    for encoding in ordered:
        try:
            text = raw.decode(encoding, errors="strict").replace("\x00", "").lstrip("\ufeff")
        except (UnicodeDecodeError, LookupError):
            continue

        if not text.strip():
            continue

        sample = "\n".join(text.splitlines()[:20])
        score = 0

        if "," in sample or ";" in sample or "\t" in sample:
            score += 5

        if any(
            token in sample.lower()
            for token in (
                "page path",
                "landing page",
                "active users",
                "sessions",
                "event count",
                "device category",
                "country",
                "city",
                "query",
                "impressions",
            )
        ):
            score += 10

        if sample.count("\ufffd") == 0:
            score += 2

        if score > best_score:
            best_text = text
            best_score = score

        if score >= 15:
            return text

    return best_text


def _strip_metadata_lines(text: str) -> str:
    """Remove leading GA4 comment/blank metadata rows without touching data rows."""
    lines = text.splitlines()
    start = 0

    for i, line in enumerate(lines):
        clean = line.replace("\x00", "").strip()
        if not clean or clean.startswith("#"):
            continue
        start = i
        break
    else:
        return ""

    return "\n".join(lines[start:])


def get_skip_rows(filepath: Path, encoding: str = "utf-8") -> int:
    """Count leading blank/comment rows."""
    path = Path(filepath)
    if not path.exists():
        return 0

    try:
        raw = path.read_bytes().replace(b"\x00", b"")
        text = raw.decode(encoding, errors="ignore").replace("\x00", "")
    except Exception as exc:
        logger.warning("Could not inspect %s with encoding %s: %s", path, encoding, exc)
        return 0

    skip = 0
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith("#") or not clean:
            skip += 1
        else:
            break
    return skip


def _read_csv_text(text: str) -> pd.DataFrame:
    """Parse CSV text, retrying with bad-line skipping only when necessary."""
    cleaned_text = _strip_metadata_lines(text)
    if not cleaned_text.strip():
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            StringIO(cleaned_text),
            engine="python",
            na_values=list(CUSTOM_NA_VALUES),
            keep_default_na=True,
        )
    except (pd.errors.ParserError, ValueError):
        df = pd.read_csv(
            StringIO(cleaned_text),
            engine="python",
            on_bad_lines="skip",
            na_values=list(CUSTOM_NA_VALUES),
            keep_default_na=True,
        )

    if df.empty:
        return df

    df.columns = [
        str(col).replace("\ufeff", "").replace("\x00", "").strip()
        for col in df.columns
    ]
    df = df.dropna(how="all").copy()

    for column in df.columns:
        if pd.api.types.is_object_dtype(df[column]):
            df[column] = df[column].map(
                lambda value: value.replace("\x00", "").strip()
                if isinstance(value, str)
                else value
            )

    return df


def load_csv_file(filepath: Union[str, Path]) -> pd.DataFrame:
    """Load a CSV robustly across GA4 export formats."""
    path = Path(filepath)
    if not path.exists():
        logger.warning("File not found: %s", path)
        return pd.DataFrame()

    try:
        raw = path.read_bytes()
    except OSError as exc:
        logger.error("Could not read %s: %s", path, exc)
        return pd.DataFrame()

    if not raw.strip():
        logger.warning("Empty CSV: %s", path)
        return pd.DataFrame()

    text = _decode_bytes(raw)
    if not text:
        logger.error("Could not decode CSV: %s", path)
        return pd.DataFrame()

    try:
        df = _read_csv_text(text)
    except Exception as exc:
        logger.exception("Failed parsing CSV %s: %s", path, exc)
        return pd.DataFrame()

    if df.empty:
        logger.warning("CSV loaded but contained no usable rows: %s", path)
        return df

    df.attrs["source_file"] = path.name
    return df


def _normalized_columns(df: pd.DataFrame) -> list[str]:
    return [
        str(column).replace("\ufeff", "").strip().lower()
        for column in df.columns
    ]


def _has_any_column(cols: Iterable[str], values: Iterable[str]) -> bool:
    values = tuple(values)
    return any(value in cols for value in values)


def _detect_dataset_type(file: Path, df: pd.DataFrame) -> str | None:
    """Determine dataset type, giving exact filenames higher priority."""
    filename = file.name.lower()
    cols = _normalized_columns(df)

    # 1. Strong filename signatures. These must run before generic column rules.
    for marker, dataset_type in FILENAME_DATASET_RULES:
        if marker in filename:
            return dataset_type

    # 2. Flexible structural signatures for GSC and GA4 exports.
    if any("device" in c for c in cols) and _has_any_column(cols, ("active users", "sessions", "views", "clicks", "impressions")):
        return "device"

    if "session source / medium" in cols:
        return "overall"

    if "event name" in cols:
        return "events"

    if "landing page + query string" in cols and (
        "sessions" in cols or "event count" in cols
    ):
        return "course_performance"

    if any("query" in c for c in cols) and _has_any_column(cols, ("clicks", "impressions")):
        return "course_gsc_queries"

    if "country" in cols or "city" in cols:
        return "geo"

    page_columns = any(
        ("page" in column) or ("landing" in column) or ("url" in column)
        for column in cols
    )
    if page_columns:
        if any("blog" in column for column in cols) or "blog" in filename:
            return "blog"
        if any("course" in column for column in cols) or "course" in filename:
            return "course"
        return "pages_generic"

    return None


def _merge_gsc_into_ga4(df_ga4: pd.DataFrame, df_gsc: pd.DataFrame) -> pd.DataFrame:
    """Seamlessly merge GSC Clicks, Impressions, Position, and CTR into GA4 Dataset."""
    if df_ga4.empty or df_gsc.empty:
        return df_ga4

    # Detect GA4 page path column
    ga4_page_col = None
    for col in df_ga4.columns:
        if any(k in str(col).lower() for k in ["path", "url", "page"]):
            ga4_page_col = col
            break

    # Detect GSC top pages column
    gsc_page_col = None
    for col in df_gsc.columns:
        if any(k in str(col).lower() for k in ["top pages", "page", "url"]):
            gsc_page_col = col
            break

    if not ga4_page_col or not gsc_page_col:
        return df_ga4

    df_ga4_copy = df_ga4.copy()
    df_gsc_copy = df_gsc.copy()

    df_ga4_copy["_norm_path"] = df_ga4_copy[ga4_page_col].apply(clean_url_to_path)
    df_gsc_copy["_norm_path"] = df_gsc_copy[gsc_page_col].apply(clean_url_to_path)

    # Format GSC CTR column safely regardless of dtype (object, string, or arrow)
    if "CTR" in df_gsc_copy.columns:
        ctr_clean = (
            df_gsc_copy["CTR"]
            .astype(str)
            .str.rstrip("%")
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df_gsc_copy["CTR_GSC"] = pd.to_numeric(ctr_clean, errors="coerce").fillna(0.0)

    # Clean integer metrics from GSC
    for num_col in ["Clicks", "Impressions", "Position"]:
        if num_col in df_gsc_copy.columns:
            cleaned_val = (
                df_gsc_copy[num_col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df_gsc_copy[num_col] = pd.to_numeric(cleaned_val, errors="coerce").fillna(0)

    # Select available metrics from GSC
    gsc_cols = ["_norm_path"]
    for c in ["Clicks", "Impressions", "CTR_GSC", "Position"]:
        if c in df_gsc_copy.columns:
            gsc_cols.append(c)

    df_gsc_sub = df_gsc_copy[gsc_cols].drop_duplicates(subset=["_norm_path"])

    # Perform left join
    merged = pd.merge(df_ga4_copy, df_gsc_sub, on="_norm_path", how="left")

    # Clean numeric columns post-merge
    for c in ["Clicks", "Impressions", "CTR_GSC", "Position"]:
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0)

    # Populate CTR in merged frame if missing or 0
    if "CTR_GSC" in merged.columns:
        if "CTR" not in merged.columns:
            merged["CTR"] = merged["CTR_GSC"]
        else:
            ga4_ctr_clean = (
                merged["CTR"]
                .astype(str)
                .str.rstrip("%")
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            ga4_ctr_num = pd.to_numeric(ga4_ctr_clean, errors="coerce").fillna(0.0)
            merged["CTR"] = np.where(ga4_ctr_num > 0, ga4_ctr_num, merged["CTR_GSC"])

    # Fallback Sessions to Clicks if GA4 Sessions are zero
    if "Sessions" in merged.columns and "Clicks" in merged.columns:
        sess_num = pd.to_numeric(
            merged["Sessions"].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        ).fillna(0)
        merged["Sessions"] = np.where(sess_num > 0, sess_num, merged["Clicks"])

    merged.drop(columns=["_norm_path"], inplace=True, errors="ignore")
    return merged


def detect_and_load_all(
    data_dir: Path = Path("data/input"),
) -> Dict[str, pd.DataFrame]:
    """
    Load all CSVs and assign stable dataset keys without overwriting.
    Automatically merges GSC Pages data into Course and Blog datasets.
    """
    data_dir = Path(data_dir)
    datasets: Dict[str, pd.DataFrame] = {}

    if not data_dir.exists():
        logger.warning("Data directory does not exist: %s", data_dir)
        return datasets

    for file in sorted(data_dir.glob("*.csv")):
        df = load_csv_file(file)
        if df.empty:
            continue

        dataset_type = _detect_dataset_type(file, df)
        if not dataset_type:
            logger.info("Skipping unrecognized CSV: %s", file.name)
            continue

        if dataset_type in datasets:
            existing = datasets[dataset_type]
            existing_source = existing.attrs.get("source_file", "unknown")
            logger.warning(
                "Multiple CSVs detected for dataset '%s'. Keeping %s and "
                "skipping %s.",
                dataset_type,
                existing_source,
                file.name,
            )
            continue

        df.attrs["source_file"] = file.name
        df.attrs["dataset_type"] = dataset_type
        datasets[dataset_type] = df
        logger.info(
            "Loaded %-18s rows=%s cols=%s source=%s",
            dataset_type,
            len(df),
            len(df.columns),
            file.name,
        )

    # Perform automated GSC-GA4 Merge for Course and Blog datasets
    if "course" in datasets and "course_gsc_pages" in datasets:
        datasets["course"] = _merge_gsc_into_ga4(datasets["course"], datasets["course_gsc_pages"])

    if "blog" in datasets and "blog_gsc_pages" in datasets:
        datasets["blog"] = _merge_gsc_into_ga4(datasets["blog"], datasets["blog_gsc_pages"])

    # Alias assignments so older Streamlit page scripts find expected keys seamlessly
    if "gsc_queries" not in datasets and "course_gsc_queries" in datasets:
        datasets["gsc_queries"] = datasets["course_gsc_queries"]

    if "geo" not in datasets:
        if "geo_pagepath" in datasets:
            datasets["geo"] = datasets["geo_pagepath"]
        elif "geo_global" in datasets:
            datasets["geo"] = datasets["geo_global"]

    if "countries" not in datasets:
        if "course_gsc_countries" in datasets:
            datasets["countries"] = datasets["course_gsc_countries"]

    return datasets