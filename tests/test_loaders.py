import pandas as pd
from pathlib import Path
from src.data.loaders import get_skip_rows

def test_skip_ga4_headers(tmp_path):
    mock_csv = tmp_path / "test_ga4.csv"
    mock_csv.write_text(
        "# Google Analytics Report\n"
        "# Created on 2026-09-23\n"
        "Page path and screen class,Views,Active users\n"
        "/blog/test-article,100,50\n"
    )
    
    skip_count = get_skip_rows(mock_csv)
    assert skip_count == 2