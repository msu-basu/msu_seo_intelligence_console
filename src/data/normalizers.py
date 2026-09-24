"""Reusable normalization helpers for course/page analytics."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml


# Internal course levels kept compatible with the mapping YAML and existing helpers.
INTERNAL_LEVEL_LABELS = {
    "PhD": "PhD",
    "Diploma": "Diploma",
    "Postgraduate": "Postgraduate",
    "Undergraduate": "Undergraduate",
    "Other": "Other",
}

DISPLAY_LEVEL_LABELS = {
    "PhD": "PhD / Doctoral",
    "Diploma": "Diploma",
    "Postgraduate": "Master (Postgraduate)",
    "Undergraduate": "Bachelor (Undergraduate)",
    "Other": "Other Certificate Programs",
}


def normalize_url_path(value: object) -> str:
    """Normalize a URL/page-path value for matching and display."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""

    text = str(value).replace("\x00", "").strip()
    if not text or text.lower() in {"nan", "none", "null", "(not set)"}:
        return ""

    # Strip query strings/fragments first.
    text = re.split(r"[?#]", text, maxsplit=1)[0]

    # Decode common URL-encoded separators without requiring urllib on every call.
    text = text.replace("%2F", "/").replace("%2f", "/")
    text = text.replace("%20", " ")

    # Remove protocol + host where present.
    text = re.sub(r"^https?://[^/]+", "", text, flags=re.IGNORECASE)

    # Handle malformed values such as /homehttps:/www.msu.edu.in/course/...
    # by extracting a genuine MSU course path. Do not treat unrelated assets such
    # as /public/storage/courses/... as course pages.
    if re.search(r"msu\.edu\.in/course(?:s)?/", text, flags=re.IGNORECASE):
        course_match = re.search(
            r"/course(?:s)?/[^?#\s]*",
            text,
            flags=re.IGNORECASE,
        )
        if course_match and not re.search(
            r"^/course(?:s)?/",
            text,
            flags=re.IGNORECASE,
        ):
            text = course_match.group(0)

    text = text.strip()
    if not text.startswith("/"):
        text = "/" + text

    # Normalize repeated slashes while preserving a single leading slash.
    text = "/" + re.sub(r"/+", "/", text.lstrip("/"))
    return text.rstrip("/") if text != "/" else text


def _course_text(path: object) -> str:
    """Return normalized lowercase text suitable for course-level matching."""
    normalized = normalize_url_path(path).lower()
    # Convert punctuation/separators into spaces so tokens such as b-tech and b tech
    # can be matched consistently.
    text = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", text).strip()


def categorize_course_url(path: object) -> str:
    """
    Categorize a course URL using the observed MSU URL/program patterns.

    Priority is intentionally:
        PhD -> Diploma -> Postgraduate -> Undergraduate -> Other

    This prevents a phrase such as "Postgraduate Diploma" from being classified
    as Postgraduate and handles doctoral/research wording before generic tokens.
    """
    text = _course_text(path)
    if not text:
        return "Other"

    compact = text.replace(" ", "")

    # 1. PhD / Doctoral
    phd_patterns = (
        r"\bphd\b",
        r"\bph d\b",
        r"\bdoctor(?:al|ate)?\b",
        r"\bdoctor of philosophy\b",
        r"\bdoctor\b.*\bphilosophy\b",
    )
    if any(re.search(pattern, text) for pattern in phd_patterns):
        return "PhD"

    # 2. Diploma
    diploma_patterns = (
        r"\bdiploma\b",
        r"\bpolytechnic\b",
        r"\bpgd\b",
        r"\bpg diploma\b",
        r"\bprofessional diploma\b",
        r"\bd pharm\b",
        r"\bd-pharm\b",
    )
    if any(re.search(pattern, text) for pattern in diploma_patterns):
        return "Diploma"
    if "dpharm" in compact:
        return "Diploma"

    # 3. Postgraduate / Master
    postgraduate_patterns = (
        r"\bmaster\b",
        r"\bmasters\b",
        r"\bpostgraduate\b",
        r"\bpg\b",
        r"\bm tech\b",
        r"\bmtech\b",
        r"\bm sc\b",
        r"\bmsc\b",
        r"\bm ca\b",
        r"\bmca\b",
        r"\bmba\b",
        r"\bm com\b",
        r"\bmcom\b",
        r"\bm pharm\b",
        r"\bmpharm\b",
        r"\bm ed\b",
        r"\bmed\b",
        r"\bm des\b",
        r"\bmdes\b",
        r"\bllm\b",
        r"\bma\b",
        r"\bms\b",
        r"\bm voc\b",
        r"\bmvoc\b",
    )
    if any(re.search(pattern, text) for pattern in postgraduate_patterns):
        return "Postgraduate"

    # 4. Undergraduate / Bachelor
    undergraduate_patterns = (
        r"\bbachelor\b",
        r"\bbachelors\b",
        r"\bundergraduate\b",
        r"\bug\b",
        r"\bb tech\b",
        r"\bbtech\b",
        r"\bb sc\b",
        r"\bbsc\b",
        r"\bb ca\b",
        r"\bbca\b",
        r"\bb ba\b",
        r"\bbba\b",
        r"\bb com\b",
        r"\bbcom\b",
        r"\bb pharm\b",
        r"\bbpharm\b",
        r"\bllb\b",
        r"\bb ed\b",
        r"\bbed\b",
        r"\bb des\b",
        r"\bbdes\b",
        r"\bb arch\b",
        r"\bbarch\b",
        r"\bb voc\b",
        r"\bbvoc\b",
        r"\bba\b",
    )
    if any(re.search(pattern, text) for pattern in undergraduate_patterns):
        return "Undergraduate"

    return "Other"


def categorize_program_level(path: object) -> str:
    """Return the display label used by the Streamlit course dashboard."""
    return DISPLAY_LEVEL_LABELS[categorize_course_url(path)]


def is_course_path(value: object) -> bool:
    """Return True only for actual /course/... or /courses/... page paths."""
    normalized = normalize_url_path(value)
    return bool(
        re.match(r"^/courses?/[^?#]+", normalized, flags=re.IGNORECASE)
    )


def find_course_page_column(
    df: pd.DataFrame,
    preferred: Iterable[str] | None = None,
) -> str:
    """
    Find the most likely URL/page-path column.

    Exact GA4 course exports use `Page path and screen class`, but this function
    also supports landing-page, URL, and generic page-path exports. Column names
    alone are not trusted; sample values are scored for URL/course evidence.
    """
    if df.empty or len(df.columns) == 0:
        raise ValueError("Cannot find a page column in an empty dataframe.")

    preferred = list(preferred or [])

    def normalized_name(column: object) -> str:
        return re.sub(r"\s+", " ", str(column).strip().lower())

    scores: dict[str, int] = {}

    preferred_rank = {
        normalized_name("Page path and screen class"): 120,
        normalized_name("Page path"): 115,
        normalized_name("Landing page + query string"): 110,
        normalized_name("Landing page"): 105,
        normalized_name("Page location"): 100,
        normalized_name("URL"): 95,
    }
    for i, column in enumerate(preferred):
        preferred_rank[normalized_name(column)] = max(
            preferred_rank.get(normalized_name(column), 0), 130 - i
        )

    for column in df.columns:
        name = normalized_name(column)
        score = preferred_rank.get(name, 0)

        if "page path and screen class" in name:
            score += 100
        elif "landing page + query string" in name:
            score += 90
        elif "landing page" in name:
            score += 80
        elif "page path" in name:
            score += 75
        elif "page location" in name:
            score += 70
        elif "url" in name:
            score += 65
        elif "course" in name:
            score += 55
        elif "page" in name:
            score += 35

        # Strong penalties for columns that look like identifiers/metrics/date fields.
        if any(token in name for token in ("date", "id", "views", "users", "sessions")):
            score -= 50

        try:
            sample = df[column].dropna().astype(str).str.strip().head(250)
        except Exception:
            sample = pd.Series(dtype="object")

        if not sample.empty:
            lower = sample.str.lower()
            course_hits = lower.str.contains(
                r"/course(?:s)?/|msu\.edu\.in/course|btech|b-tech|bachelor|bachelors|"
                r"\bbsc\b|b-sc|mba|master|m-sc|diploma|phd|doctor",
                regex=True,
                na=False,
            ).sum()
            path_hits = lower.str.contains(
                r"^/|https?://|www\.",
                regex=True,
                na=False,
            ).sum()

            score += min(int(course_hits), 50)
            score += min(int(path_hits), 20)

        scores[str(column)] = score

    return max(
        df.columns,
        key=lambda c: scores.get(str(c), -10_000),
    )


def clean_course_name(path: object) -> str:
    """Convert a course URL/path into a readable course title."""
    normalized = normalize_url_path(path)
    if not normalized:
        return "Unknown Program"

    # Prefer the content after /course/ or /courses/ when available.
    match = re.search(
        r"/course(?:s)?/([^?#]+)",
        normalized,
        flags=re.IGNORECASE,
    )
    clean = match.group(1) if match else normalized.lstrip("/")

    clean = clean.strip(" /").replace("-", " ").replace("_", " ").replace("/", " - ")
    clean = re.sub(r"\s+", " ", clean).strip()

    replacements = [
        (r"\bb[\s-]?tech\b", "B.Tech"),
        (r"\bm[\s-]?tech\b", "M.Tech"),
        (r"\bm[\s-]?sc\b", "M.Sc"),
        (r"\bb[\s-]?sc\b", "B.Sc"),
        (r"\bb[\s-]?pharm\b", "B.Pharm"),
        (r"\bm[\s-]?pharm\b", "M.Pharm"),
        (r"\bb[\s-]?voc\b", "B.Voc"),
        (r"\bm[\s-]?voc\b", "M.Voc"),
        (r"\bbba\b", "BBA"),
        (r"\bbca\b", "BCA"),
        (r"\bbcom\b", "B.Com"),
        (r"\bba\b", "BA"),
        (r"\bb ed\b|\bbed\b", "B.Ed"),
        (r"\bbdes\b", "B.Des"),
        (r"\bbarch\b", "B.Arch"),
        (r"\bllb\b", "LLB"),
        (r"\bmba\b", "MBA"),
        (r"\bmca\b", "MCA"),
        (r"\bmcom\b", "M.Com"),
        (r"\bma\b", "MA"),
        (r"\bms\b", "MS"),
        (r"\bph[\s-]?d\b", "Ph.D."),
        (r"\bdoctor of philosophy\b", "Ph.D."),
    ]
    for pattern, replacement in replacements:
        clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)

    # Title-case only ordinary words; keep known degree abbreviations readable.
    clean = clean.title()
    for code in (
        "B.Tech", "M.Tech", "B.Sc", "M.Sc", "B.Pharm", "M.Pharm",
        "B.Voc", "M.Voc", "BBA", "BCA", "B.Com", "BA", "B.Ed",
        "B.Des", "B.Arch", "LLB", "MBA", "MCA", "M.Com", "MA", "MS",
        "Ph.D.",
    ):
        clean = re.sub(re.escape(code), code, clean, flags=re.IGNORECASE)

    clean = re.sub(r"\bPh\.D\.\s+Ph\.D\.$", "Ph.D.", clean)
    return clean or "Unknown Program"


def parse_numeric_series(series: pd.Series | None, index: pd.Index) -> pd.Series:
    """Parse GA4/GSC numeric strings safely, returning a numeric series."""
    if series is None:
        return pd.Series(0.0, index=index, dtype="float64")

    cleaned = (
        series.astype(str)
        .str.replace("\x00", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
        .replace({"": None, "nan": None, "none": None, "null": None, "-": None, "N/A": None})
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def normalize_percent_series(series: pd.Series) -> pd.Series:
    """Normalize percentage values to 0-100 and round to two decimals."""
    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if not values.empty and values.max() <= 1.0 and values.max() > 0:
        values = values * 100.0
    return values.clip(lower=0).round(2)


def apply_course_metadata(
    df: pd.DataFrame,
    url_col: str = "Page path and screen class",
) -> pd.DataFrame:
    """Assign course level/name and apply optional YAML mapping overrides."""
    if df.empty or url_col not in df.columns:
        return df

    result = df.copy()
    result["Course Level"] = result[url_col].apply(categorize_course_url)

    mapping_file = Path("data/mappings/course_mapping.yaml")
    if mapping_file.exists():
        try:
            with mapping_file.open("r", encoding="utf-8") as f:
                mappings = yaml.safe_load(f) or {}

            normalized_map = {
                normalize_url_path(url): meta
                for url, meta in mappings.items()
                if isinstance(meta, dict)
            }

            normalized_urls = result[url_col].map(normalize_url_path)

            for url, meta in normalized_map.items():
                mask = normalized_urls == url
                if not mask.any():
                    continue
                if "level" in meta:
                    result.loc[mask, "Course Level"] = meta["level"]
                if "course_name" in meta:
                    result.loc[mask, "Course Name"] = meta["course_name"]

        except Exception:
            # Mapping is an optional enrichment; never prevent the dataset from loading.
            pass

    if "Course Name" not in result.columns:
        result["Course Name"] = result[url_col].apply(clean_course_name)

    return result
