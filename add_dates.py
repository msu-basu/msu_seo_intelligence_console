import os
import numpy as np
import pandas as pd


def process_ga4_file(filename):
    file_path = os.path.join("data", "input", filename)

    if not os.path.exists(file_path):
        print(f"Skipping {filename}: File not found at {file_path}")
        return

    print(f"Processing: {file_path}")

    # Find where the actual table data begins (skip metadata)
    skip_lines = 0
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if "," in line and not line.startswith("#"):
                line_lower = line.lower()
                if any(
                    k in line_lower
                    for k in ["page", "course", "blog", "views", "screen", "path"]
                ):
                    skip_lines = i
                    break

    df = pd.read_csv(file_path, skiprows=skip_lines, on_bad_lines="skip")
    df = df.dropna(how="all")

    # Detect Course/Blog and Views column names
    title_col = next(
        (
            c
            for c in df.columns
            if any(
                k in str(c).lower()
                for k in ["page", "course", "blog", "title", "item"]
            )
        ),
        df.columns[0],
    )
    views_col = next(
        (
            c
            for c in df.columns
            if any(
                k in str(c).lower()
                for k in ["view", "session", "count", "user"]
            )
        ),
        df.columns[1] if len(df.columns) > 1 else df.columns[0],
    )

    # Clean views
    df[views_col] = (
        df[views_col].astype(str).str.replace(",", "").str.replace(" ", "")
    )
    df[views_col] = (
        pd.to_numeric(df[views_col], errors="coerce").fillna(0).astype(int)
    )

    df = df[df[title_col].notna()]

    # Add 365 daily dates if Date column is missing
    if "Date" not in df.columns or df["Date"].nunique() < 30:
        dates = pd.date_range(end=pd.Timestamp.today(), periods=365, freq="D")
        expanded_rows = []

        for _, row in df.iterrows():
            total_views = row[views_col]
            daily_views = (
                np.random.multinomial(total_views, [1 / 365] * 365)
                if total_views > 0
                else [0] * 365
            )

            for date, views in zip(dates, daily_views):
                new_row = row.to_dict()
                new_row["Date"] = date.strftime("%Y-%m-%d")
                new_row[views_col] = views
                expanded_rows.append(new_row)

        df_updated = pd.DataFrame(expanded_rows)
        df_updated.to_csv(file_path, index=False)
        print(f"SUCCESS: Updated {filename} with 365 days of data.")
    else:
        df.to_csv(file_path, index=False)
        print(f"SUCCESS: Cleaned {filename}.")


# Process both Blog and Course data
process_ga4_file("01_Blog_GA4.csv")
process_ga4_file("02_Course_GA4.csv")