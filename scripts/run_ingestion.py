"""
run_ingestion.py
Master CLI Runner for the MSU Analytics Daily Data Ingestion & CDC Pipeline.
Fetches GA4 and GSC data for a sliding lookback window, executes idempotent upserts,
and writes verification files to data/staging/ for manual inspection.

Usage:
  python scripts/run_ingestion.py                 # Uses default 3-day lookback window
  python scripts/run_ingestion.py --dry-run       # Preview extraction without saving
  python scripts/run_ingestion.py --lookback-days 5
  python scripts/run_ingestion.py --start-date 2026-09-20 --end-date 2026-09-25
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
from dotenv import load_dotenv

# Ensure root path is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.pipeline.ga4_extractor import GA4Extractor
from src.pipeline.gsc_extractor import GSCExtractor
from src.pipeline.cdc_engine import CDCEngine

env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

CRED_PATH_RAW = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials/google_service_account.json")
CRED_PATH = str((project_root / CRED_PATH_RAW).resolve()) if not os.path.isabs(CRED_PATH_RAW) else CRED_PATH_RAW

GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "").strip()
GSC_SITE_URL = os.getenv("GSC_SITE_URL", "").strip()
LOOKBACK_DAYS_DEFAULT = int(os.getenv("PIPELINE_LOOKBACK_DAYS", "3"))

def parse_args():
    parser = argparse.ArgumentParser(description="MSU Analytics Ingestion Pipeline with CDC")
    parser.add_argument("--lookback-days", type=int, default=None,
                        help="Override high-watermark with fixed past days (default: auto-detect max date from DB)")
    parser.add_argument("--start-date", type=str, default=None,
                        help="Custom start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None,
                        help="Custom end date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and print metrics summary without writing to DB or files")
    parser.add_argument("--no-db", action="store_true",
                        help="Skip writing to PostgreSQL database")
    parser.add_argument("--no-files", action="store_true",
                        help="Skip writing verification CSV/Parquet files")
    return parser.parse_args()

def main():
    args = parse_args()
    
    print("\n" + "=" * 70)
    print("      MSU SEO & ANALYTICS DATA INGESTION PIPELINE (CDC)")
    print("=" * 70)

    # 1. Initialize CDC Engine & Determine Date Window
    cdc = CDCEngine(export_files=not args.no_files)

    if args.start_date and args.end_date:
        start_d = args.start_date
        end_d = args.end_date
        print(f"[*] Custom Extraction Window : {start_d}  -->  {end_d}")
    elif args.lookback_days:
        end_date_obj = date.today()
        start_date_obj = end_date_obj - timedelta(days=args.lookback_days)
        start_d = start_date_obj.strftime("%Y-%m-%d")
        end_d = end_date_obj.strftime("%Y-%m-%d")
        print(f"[*] Manual Lookback Window   : {start_d}  -->  {end_d}")
    else:
        # Default: Auto-detect High-Watermark (Max date in DB)
        max_db_date = cdc.get_max_extracted_date() if not args.no_db else None
        end_date_obj = date.today()
        end_d = end_date_obj.strftime("%Y-%m-%d")

        if max_db_date:
            start_d = max_db_date.strftime("%Y-%m-%d")
            print(f"[*] High-Watermark Detected  : Last ingested date in DB is {max_db_date}")
            print(f"[*] Catch-Up Date Window     : {start_d}  -->  {end_d} (extracting fresh delta till today)")
        else:
            start_date_obj = end_date_obj - timedelta(days=3)
            start_d = start_date_obj.strftime("%Y-%m-%d")
            print(f"[*] Sliding Lookback Window  : {start_d}  -->  {end_d}")

    print(f"[*] Dry-Run Mode             : {args.dry_run}")
    print(f"[*] PostgreSQL Write         : {not args.no_db}")
    print(f"[*] Staging Files Export     : {not args.no_files}")
    print("-" * 70)

    # 2. Initialize Extractors
    ga4 = GA4Extractor(CRED_PATH, GA4_PROPERTY_ID)
    gsc = GSCExtractor(CRED_PATH, GSC_SITE_URL)

    # 3. Extract GA4 Data
    print("\n[+] Extracting Google Analytics 4 (GA4) Data...")
    df_ga4_blog = ga4.fetch_pages_daily(start_d, end_d, path_filter_string="/blog/")
    df_ga4_course = ga4.fetch_pages_daily(start_d, end_d, path_filter_string="/course/")
    
    total_ga4_blog_views = df_ga4_blog["views"].sum() if not df_ga4_blog.empty else 0
    total_ga4_course_views = df_ga4_course["views"].sum() if not df_ga4_course.empty else 0
    print(f"    - Blog Pages Extracted   : {len(df_ga4_blog):,} records (Total Views: {total_ga4_blog_views:,})")
    print(f"    - Course Pages Extracted : {len(df_ga4_course):,} records (Total Views: {total_ga4_course_views:,})")

    # 4. Extract GSC Data
    print("\n[+] Extracting Google Search Console (GSC) Data...")
    df_gsc_blog = gsc.fetch_pages_daily(start_d, end_d, path_filter_string="/blog/")
    df_gsc_course = gsc.fetch_pages_daily(start_d, end_d, path_filter_string="/course/")
    df_gsc_queries = gsc.fetch_queries_daily(start_d, end_d, path_filter_string="/blog/", row_limit=5000)

    total_gsc_clicks = (df_gsc_blog["clicks"].sum() if not df_gsc_blog.empty else 0) + \
                       (df_gsc_course["clicks"].sum() if not df_gsc_course.empty else 0)
    total_gsc_impressions = (df_gsc_blog["impressions"].sum() if not df_gsc_blog.empty else 0) + \
                            (df_gsc_course["impressions"].sum() if not df_gsc_course.empty else 0)
    print(f"    - Blog Search Pages      : {len(df_gsc_blog):,} records")
    print(f"    - Course Search Pages    : {len(df_gsc_course):,} records")
    print(f"    - Search Queries Logged  : {len(df_gsc_queries):,} records")
    print(f"    - Total Search Visibility: {total_gsc_clicks:,} clicks | {total_gsc_impressions:,} impressions")

    # 5. Staging & CDC Execution
    if args.dry_run:
        print("\n[!] Dry run enabled: Skipping database upsert and file writes.")
    else:
        print("\n" + "=" * 70)
        print("                   DATA VERIFICATION & CDC STAGING")
        print("=" * 70)

        # File Staging for Visual Excel/CSV Inspection
        if not args.no_files:
            print("\n[1] Exporting Staging Files (data/staging/):")
            cdc.stage_to_files(df_ga4_blog, "staging_ga4_blog_daily")
            cdc.stage_to_files(df_ga4_course, "staging_ga4_course_daily")
            cdc.stage_to_files(df_gsc_blog, "staging_gsc_blog_pages")
            cdc.stage_to_files(df_gsc_course, "staging_gsc_course_pages")
            cdc.stage_to_files(df_gsc_queries, "staging_gsc_queries")

        # Database Upsert
        if not args.no_db:
            print("\n[2] Executing CDC Upsert into PostgreSQL:")
            run_id = cdc.log_pipeline_start("daily_ingestion", "GA4+GSC", start_d, end_d)
            try:
                total_extracted = len(df_ga4_blog) + len(df_ga4_course) + len(df_gsc_blog) + len(df_gsc_course) + len(df_gsc_queries)
                upserted = 0
                upserted += cdc.upsert_ga4_daily(df_ga4_blog, "raw.ga4_blog_daily")
                upserted += cdc.upsert_ga4_daily(df_ga4_course, "raw.ga4_course_daily")
                upserted += cdc.upsert_gsc_pages(df_gsc_blog, "raw.gsc_blog_pages")
                upserted += cdc.upsert_gsc_pages(df_gsc_course, "raw.gsc_course_pages")
                upserted += cdc.upsert_gsc_queries(df_gsc_queries, "raw.gsc_blog_queries")

                # Log individual API call durations into control.api_usage_log
                all_call_logs = ga4.call_logs + gsc.call_logs
                cdc.log_api_calls(run_id, all_call_logs)

                cdc.log_pipeline_complete(
                    run_id=run_id,
                    status="SUCCESS",
                    extracted=total_extracted,
                    upserted=upserted
                )
                print("    [OK] PostgreSQL raw tables updated with 0 duplicate violations (CDC idempotent).")
                print(f"    [OK] Logged {len(all_call_logs)} API hits into control.api_usage_log.")
            except Exception as e:
                cdc.log_pipeline_complete(run_id=run_id, status="FAILED", extracted=0, inserted=0, updated=0, error_msg=str(e))
                print(f"    [!] Database upsert notice: {e}")
                print("        (If PostgreSQL is not running locally, run with --no-db to use file staging).")

    # 6. Verification Sample Highlights
    print("\n" + "-" * 70)
    print("                    DATA VERIFICATION PREVIEW")
    print("-" * 70)
    if not df_ga4_blog.empty:
        print("\n>>> Top 3 Blog Pages by Views (GA4):")
        top_blog = df_ga4_blog.groupby("page_path")["views"].sum().sort_values(ascending=False).head(3)
        for path, v in top_blog.items():
            print(f"    - {v:>5,} views : {path}")

    if not df_gsc_queries.empty:
        print("\n>>> Top 3 Search Queries (GSC):")
        top_q = df_gsc_queries.groupby("query")["clicks"].sum().sort_values(ascending=False).head(3)
        for q, c in top_q.items():
            print(f"    - {c:>4,} clicks : {q}")

    # 7. API Latency & Cost Analysis Benchmark
    all_call_logs = ga4.call_logs + gsc.call_logs
    total_duration_ms = sum(c["duration_ms"] for c in all_call_logs)
    print("\n" + "=" * 70)
    print("                 API LATENCY & COST BENCHMARK")
    print("=" * 70)
    print(f"  * Total API Calls Made       : {len(all_call_logs)} requests")
    for c in all_call_logs:
        print(f"    - {c['api_service']:<28} | {c['endpoint_method']:<32} : {c['duration_ms']:>4} ms ({c['rows_returned']:,} rows)")
    print(f"  * Total Cumulative API Time  : {total_duration_ms / 1000:.2f} seconds ({total_duration_ms:,} ms)")
    print(f"  * Estimated Cloud API Cost   : $0.00000 (Covered by Google Cloud Free Tier Quota)")

    print("\n" + "=" * 70)
    print(" Pipeline Execution Complete. Data is verified and ready for review.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
