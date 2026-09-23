import os
import numpy as np
import pandas as pd

# Search for the CSV file across possible folder locations
possible_paths = [
    os.path.join("data", "input", "02_Course_GA4.csv"),
    os.path.join("input", "02_Course_GA4.csv"),
    "02_Course_GA4.csv",
]

csv_file = None
for path in possible_paths:
    if os.path.exists(path):
        csv_file = path
        break

if not csv_file:
    raise FileNotFoundError(
        "Could not find 02_Course_GA4.csv inside data/input/ or root folder."
    )

print(f"Loading CSV from: {csv_file}")

# Automatically find where the table headers start (skipping GA4 metadata lines)
skip_lines = 0
with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
    for i, line in enumerate(f):
        if "," in line and not line.startswith("#"):
            line_lower = line.lower()
            if any(k in line_lower for k in ["page", "course", "views", "screen", "path"]):
                skip_lines = i
                break

if skip_lines > 0:
    print(f"Skipping {skip_lines} GA4 metadata line(s)...")

# Read CSV skipping metadata
df = pd.read_csv(csv_file, skiprows=skip_lines, on_bad_lines="skip")
df = df.dropna(how="all")

# Auto-detect Course and Views column names
course_col = next(
    (c for c in df.columns if any(k in str(c).lower() for k in ["page", "course", "item", "title"])),
    df.columns[0],
)
views_col = next(
    (c for c in df.columns if any(k in str(c).lower() for k in ["view", "session", "count", "user"])),
    df.columns[1] if len(df.columns) > 1 else df.columns[0],
)

print(f"Detected Course Column: '{course_col}'")
print(f"Detected Views Column:  '{views_col}'")

# Clean numerical values
df[views_col] = df[views_col].astype(str).str.replace(",", "").str.replace(" ", "")
df[views_col] = pd.to_numeric(df[views_col], errors="coerce").fillna(0).astype(int)

# Filter out empty rows
df = df[df[course_col].notna()]

# Generate 365 daily dates ending today
dates = pd.date_range(end=pd.Timestamp.today(), periods=365, freq="D")
expanded_rows = []

for _, row in df.iterrows():
    total_views = row[views_col]

    if total_views <= 0:
        daily_views = [0] * 365
    else:
        daily_views = np.random.multinomial(total_views, [1 / 365] * 365)

    for date, views in zip(dates, daily_views):
        new_row = row.to_dict()
        new_row["Date"] = date.strftime("%Y-%m-%d")
        new_row[views_col] = views
        expanded_rows.append(new_row)

# Overwrite CSV with daily breakdown
df_updated = pd.DataFrame(expanded_rows)
df_updated.to_csv(csv_file, index=False)

print(f"SUCCESS: Updated {csv_file} with 365-day Date column!")