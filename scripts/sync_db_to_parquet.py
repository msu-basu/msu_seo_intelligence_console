"""
sync_db_to_parquet.py
Synchronizes local PostgreSQL raw.* tables into data/processed/*.parquet.
Ensures Streamlit Cloud (which falls back to parquet files) has 100% parity
with the local PostgreSQL database metrics, row counts, and article numbers.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.data.db_loader import (
    TABLE_SCHEMAS,
    FILE_TO_KEY_MAP,
    load_dataset_from_db,
    test_db_connection,
)


def sync_all_tables_to_parquet():
    if not test_db_connection():
        print("[ERROR] Cannot connect to PostgreSQL database. Sync aborted.")
        sys.exit(1)

    processed_dir = PROJECT_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    print("[*] Starting PostgreSQL -> Parquet Full Synchronization...")

    for fname, key in FILE_TO_KEY_MAP.items():
        if not fname.endswith(".parquet"):
            continue

        target_file = processed_dir / fname
        print(f"  -> Syncing '{key}' -> {fname}...")
        df = load_dataset_from_db(key)

        if df.empty:
            print(f"     [WARN] '{key}' returned 0 rows from DB. Skipping.")
            continue

        # Format columns appropriately
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        int_cols = ["Views", "Active users", "Event count", "Key events", "Total revenue", "Clicks", "Impressions", "Sessions"]
        for c in int_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")

        float_cols = ["Bounce rate", "Views per active user", "Average engagement time per active user", "CTR", "Position", "Engagement rate"]
        for c in float_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype("float64")

        df.to_parquet(target_file, index=False)
        print(f"     [OK] Saved {len(df):,} rows to {target_file.name}")

    print("\n[SUCCESS] All Parquet files are fully synchronized with PostgreSQL!")


if __name__ == "__main__":
    sync_all_tables_to_parquet()
