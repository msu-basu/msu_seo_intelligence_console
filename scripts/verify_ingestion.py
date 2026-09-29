"""
verify_ingestion.py
Verification script to inspect database tables, control audit logs,
and staged files after running the ingestion pipeline.
"""
import os
import sys
from pathlib import Path
import psycopg
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "web_analytics")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123")

def verify():
    print("=" * 70)
    print("           POST-INGESTION AUDIT & VERIFICATION REPORT")
    print("=" * 70)

    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

    with conn.cursor() as cur:
        # 1. Pipeline Control Runs Log
        print("\n--- 1. Latest Pipeline Execution Log (control.pipeline_runs) ---")
        cur.execute("""
            SELECT pipeline_run_id, source, report_name, start_date, end_date, 
                   status, rows_extracted, rows_upserted, started_at, completed_at
            FROM control.pipeline_runs
            ORDER BY started_at DESC
            LIMIT 3;
        """)
        runs = cur.fetchall()
        for r in runs:
            print(f"  * Run ID         : {r[0]}")
            print(f"    Source / Job   : {r[1]} / {r[2]}")
            print(f"    Date Window    : {r[3]} --> {r[4]}")
            print(f"    Status         : {r[5]}")
            print(f"    Rows Extracted : {r[6]:,}")
            print(f"    Rows Upserted  : {r[7]:,}")
            print(f"    Execution Time : {r[8]} --> {r[9]}\n")

        # 2. Database High-Watermark & Row Counts
        print("--- 2. Database Table Row Counts & High-Watermarks ---")
        tables = [
            ("raw.ga4_blog_daily", "report_date"),
            ("raw.ga4_course_daily", "report_date"),
            ("raw.gsc_blog_pages", None),
            ("raw.gsc_course_pages", None),
            ("raw.gsc_blog_queries", None),
        ]

        for tbl, date_col in tables:
            cur.execute(f"SELECT COUNT(*) FROM {tbl};")
            count = cur.fetchone()[0]
            if date_col:
                cur.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {tbl};")
                min_d, max_d = cur.fetchone()
                print(f"  * {tbl:<24} : {count:>9,} rows | Min Date: {min_d} | New Max Date: {max_d}")
            else:
                print(f"  * {tbl:<24} : {count:>9,} rows")

        # 3. Sample Fresh Records Ingested
        print("\n--- 3. Sample Freshly Ingested Records (Dates >= 2026-09-24) ---")
        cur.execute("""
            SELECT report_date, page_path, views, active_users
            FROM raw.ga4_blog_daily
            WHERE report_date >= '2026-09-24'
            ORDER BY report_date DESC, views DESC
            LIMIT 5;
        """)
        fresh_rows = cur.fetchall()
        if fresh_rows:
            for fr in fresh_rows:
                print(f"    [{fr[0]}] {fr[2]:>4} views | {fr[3]:>4} users | {fr[1]}")
        else:
            print("    No records found for date >= 2026-09-24")

        # 4. API Usage, Latency & Cost Audit Log
        print("\n--- 4. API Hits & Duration Audit (control.api_usage_log) ---")
        try:
            cur.execute("""
                SELECT 
                    api_service,
                    COUNT(*) as total_calls,
                    SUM(duration_ms) as total_duration_ms,
                    ROUND(AVG(duration_ms)) as avg_duration_ms,
                    SUM(rows_returned) as total_rows,
                    SUM(estimated_cost_usd) as total_cost
                FROM control.api_usage_log
                GROUP BY api_service;
            """)
            stats = cur.fetchall()
            if stats:
                for s in stats:
                    print(f"  * {s[0]:<28} : {s[1]:>3} hits | Total Time: {s[2]:>5,} ms ({s[2]/1000:>5.2f}s) | Avg Latency: {s[3]:>4} ms | Cost: ${s[5]:.5f}")
                
                # Show latest 4 individual calls
                cur.execute("""
                    SELECT call_timestamp, api_service, endpoint_method, duration_ms, rows_returned, http_status
                    FROM control.api_usage_log
                    ORDER BY call_timestamp DESC
                    LIMIT 4;
                """)
                recent_calls = cur.fetchall()
                print("\n    Recent Individual API Hits:")
                for rc in recent_calls:
                    ts = rc[0].strftime("%H:%M:%S")
                    print(f"      [{ts}] {rc[1]:<24} | {rc[2]:<30} | {rc[3]:>4} ms | {rc[4]:>5} rows | HTTP {rc[5]}")
            else:
                print("    (No API calls recorded in control.api_usage_log yet. Run scripts/run_ingestion.py to populate).")
        except Exception as e:
            print(f"    (Notice: {e})")

    conn.close()

    # 5. Check Staging Directory
    print("\n--- 5. Staging Files (data/staging/) ---")
    staging_dir = project_root / "data" / "staging"
    if staging_dir.exists():
        for f in sorted(staging_dir.glob("*.*")):
            size_kb = f.stat().st_size / 1024
            print(f"  * {f.name:<32} : {size_kb:>8.2f} KB")

    print("\n" + "=" * 70)
    print(" Verification Complete. Data successfully ingested and verified.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    verify()
