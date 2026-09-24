from pathlib import Path

from src.data.loaders import detect_and_load_all, get_skip_rows, load_csv_file


def test_skip_ga4_headers(tmp_path):
    mock_csv = tmp_path / "test_ga4.csv"
    mock_csv.write_text(
        "# Google Analytics Report\n"
        "# Created on 2026-09-23\n"
        "Page path and screen class,Views,Active users\n"
        "/blog/test-article,100,50\n",
        encoding="utf-8",
    )

    skip_count = get_skip_rows(mock_csv)
    assert skip_count == 2


def test_load_csv_with_utf8_bom_and_null_bytes(tmp_path):
    mock_csv = tmp_path / "utf8_bom.csv"
    content = (
        "\ufeff# GA4 export\n"
        "# metadata\n"
        "Page path and screen class,Views,Active users\n"
        "/course/test,\x00100\x00,50\n"
    )
    mock_csv.write_text(content, encoding="utf-8-sig")

    df = load_csv_file(mock_csv)

    assert list(df.columns) == [
        "Page path and screen class",
        "Views",
        "Active users",
    ]
    assert df.iloc[0]["Page path and screen class"] == "/course/test"
    assert str(df.iloc[0]["Views"]).replace(".0", "") == "100"


def test_load_csv_with_utf16_le(tmp_path):
    mock_csv = tmp_path / "utf16_le.csv"
    content = (
        "# GA4 export\n"
        "# metadata\n"
        "Page path and screen class,Views,Active users\n"
        "/course/test,100,50\n"
    )
    mock_csv.write_bytes(content.encode("utf-16-le"))

    df = load_csv_file(mock_csv)

    assert not df.empty
    assert "Page path and screen class" in df.columns
    assert df.iloc[0]["Views"] == 100


def test_course_dataset_is_not_overwritten_by_course_performance(tmp_path):
    course = tmp_path / "02_Course_GA4.csv"
    course.write_text(
        "# GA4\n"
        "Page path and screen class,Views,Active users,Key events\n"
        "/course/btech-test,100,50,3\n",
        encoding="utf-8",
    )

    performance = tmp_path / "03_Course_Performance.csv"
    performance.write_text(
        "# GA4\n"
        "Landing page + query string,Sessions,Event count,Engagement rate\n"
        "/course/btech-test,10,3,1\n",
        encoding="utf-8",
    )

    datasets = detect_and_load_all(tmp_path)

    assert datasets["course"].attrs["source_file"] == "02_Course_GA4.csv"
    assert datasets["course"]["Page path and screen class"].iloc[0] == "/course/btech-test"
    assert datasets["course_performance"].attrs["source_file"] == "03_Course_Performance.csv"
