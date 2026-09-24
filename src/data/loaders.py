"""Robust CSV loading and dataset detection for the MSU SEO console."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Dict, Iterable, Union

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

# Exact/strong filename rules take precedence over generic column signatures.
FILENAME_DATASET_RULES = (
    ("00_overall", "overall"),
    ("01_blog", "blog"),
    ("02_course_ga4", "course"),
    ("02_course", "course"),
    ("03_course_performance", "course_performance"),
    ("04_device", "device"),
    ("05_events", "events"),
    ("06_geo_global", "geo"),
    ("06_geo_pagepath", "geo_pagepath"),
)


def _decode_bytes(raw: bytes) -> str:
    """Decode bytes using BOM-aware and null-byte-aware encoding detection."""
    if not raw:
        return ""

    # Never strip NUL bytes before trying UTF-16: in UTF-16 they are valid byte
    # pairs (for example '#\\x00') and removing them would corrupt every character.
    if raw.startswith(b"\xef\xbb\xbf"):
        ordered = ("utf-8-sig", "utf-8", "cp1252", "latin1")
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        ordered = ("utf-16", "utf-16-le", "utf-16-be")
    else:
        nul_ratio = raw.count(b"\x00") / max(len(raw), 1)
        if nul_ratio > 0.15:
            # Strong signal for UTF-16 without a BOM.
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
    """
    Count leading blank/comment rows.

    Retained for compatibility with the existing tests and utilities.
    """
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
        df = pd.read_csv(StringIO(cleaned_text), engine="python")
    except (pd.errors.ParserError, ValueError):
        # GA4 free-form exports can contain a final "Grand total" row with one
        # extra field. Retry by skipping only structurally bad lines.
        df = pd.read_csv(
            StringIO(cleaned_text),
            engine="python",
            on_bad_lines="skip",
        )

    if df.empty:
        return df

    df.columns = [
        str(col).replace("\ufeff", "").replace("\x00", "").strip()
        for col in df.columns
    ]
    df = df.dropna(how="all").copy()

    # Remove null bytes from string cells without coercing the entire frame to str.
    for column in df.columns:
        if pd.api.types.is_object_dtype(df[column]):
            df[column] = df[column].map(
                lambda value: value.replace("\x00", "").strip()
                if isinstance(value, str)
                else value
            )

    return df


def load_csv_file(filepath: Union[str, Path]) -> pd.DataFrame:
    """
    Load a CSV robustly across GA4 export formats.

    Handles:
      - leading `#` metadata rows
      - blank metadata lines
      - UTF-8 / UTF-8 BOM
      - UTF-16 / UTF-16 LE / UTF-16 BE
      - CP1252 / Latin-1 fallback
      - embedded NUL characters
      - malformed "Grand total" rows via a controlled parser retry
    """
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

    # 2. Strong structural signatures.
    if "device category" in cols and (
        _has_any_column(cols, ("active users", "sessions", "views"))
    ):
        return "device"

    if "session source / medium" in cols:
        return "overall"

    if "event name" in cols:
        return "events"

    if "landing page + query string" in cols and (
        "sessions" in cols or "event count" in cols
    ):
        return "course_performance"

    if "query" in cols and _has_any_column(cols, ("clicks", "impressions")):
        return "gsc_queries"

    if "country" in cols or "city" in cols:
        return "geo"

    page_columns = any(
        ("page path" in column)
        or ("landing page" in column)
        or ("page location" in column)
        or ("url" in column)
        for column in cols
    )
    if page_columns:
        if any("blog" in column for column in cols):
            return "blog"
        if any("course" in column for column in cols):
            return "course"
        return "pages_generic"

    return None


def detect_and_load_all(
    data_dir: Path = Path("data/input"),
) -> Dict[str, pd.DataFrame]:
    """
    Load all CSVs and assign stable dataset keys.

    Crucially, `03_Course_Performance.csv` is stored under `course_performance`
    and can no longer overwrite the true `02_Course_GA4.csv` course dataset.
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

        # Never silently overwrite a dataset that was already assigned.
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

    return datasets
