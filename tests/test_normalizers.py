import pandas as pd

from src.data.normalizers import (
    categorize_course_url,
    categorize_program_level,
    clean_course_name,
    find_course_page_column,
    normalize_percent_series,
)


def test_course_categories_from_realistic_slugs():
    assert categorize_program_level("/course/btech-in-artificial-intelligence-and-machine-learning") == "Bachelor (Undergraduate)"
    assert categorize_program_level("/course/m-sc-in-medical-radiology-and-imaging-technology") == "Master (Postgraduate)"
    assert categorize_program_level("/course/doctor-of-philosophy-phd") == "PhD / Doctoral"
    assert categorize_program_level("/course/d-pharm-in-pharmacy") == "Diploma"


def test_diploma_has_priority_over_postgraduate():
    assert categorize_course_url("/course/postgraduate-diploma-in-management") == "Diploma"


def test_course_page_column_prefers_actual_ga4_field():
    df = pd.DataFrame(
        {
            "Date": ["20260923"],
            "Views": [100],
            "Active users": [50],
            "Page path and screen class": ["/course/btech-test"],
        }
    )
    assert find_course_page_column(df) == "Page path and screen class"


def test_clean_course_name():
    assert clean_course_name("/course/btech-in-artificial-intelligence-and-machine-learning").startswith(
        "B.Tech In Artificial Intelligence"
    )
    assert clean_course_name("/course/doctor-of-philosophy-phd") == "Ph.D."


def test_percent_normalization():
    assert normalize_percent_series(pd.Series([0.973659, 0.25])).tolist() == [97.37, 25.0]
    assert normalize_percent_series(pd.Series([3.14159, 0.42, 2.0])).tolist() == [3.14, 0.42, 2.0]
