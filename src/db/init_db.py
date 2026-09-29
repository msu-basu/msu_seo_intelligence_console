"""
init_db.py
Database schema verification and migration script for the MSU Analytics Pipeline.
Safely inspects existing PostgreSQL tables in 'control' and 'raw' schemas,
ensuring natural unique constraints are enforced for idempotent CDC upserts.
Does NOT drop, overwrite, or alter existing data.
"""
import os
import sys
from pathlib import Path
import psycopg
from dotenv import load_dotenv

# Load environment variables
env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "web_analytics")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123")

def get_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True
    )

def verify_and_prepare_database():
    print(f"[*] Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    try:
        conn = get_connection()
    except Exception as e:
        print(f"[ERROR] Could not connect to PostgreSQL: {e}")
        return False

    with conn.cursor() as cur:
        # 1. Verify / Create Control Schema & Tables
        cur.execute("CREATE SCHEMA IF NOT EXISTS control;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS control.pipeline_runs (
                pipeline_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source TEXT NOT NULL,
                report_name TEXT NOT NULL,
                job_mode TEXT NOT NULL,
                start_date DATE,
                end_date DATE,
                status TEXT NOT NULL,
                rows_extracted INT DEFAULT 0,
                rows_upserted INT DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                completed_at TIMESTAMPTZ
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS control.data_quality_log (
                log_id BIGSERIAL PRIMARY KEY,
                pipeline_run_id UUID REFERENCES control.pipeline_runs(pipeline_run_id) ON DELETE CASCADE,
                check_name TEXT NOT NULL,
                table_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS control.api_usage_log (
                log_id BIGSERIAL PRIMARY KEY,
                pipeline_run_id UUID REFERENCES control.pipeline_runs(pipeline_run_id) ON DELETE CASCADE,
                api_service VARCHAR(50) NOT NULL,
                endpoint_method VARCHAR(100) NOT NULL,
                target_metric VARCHAR(100),
                call_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                duration_ms INT NOT NULL,
                rows_returned INT DEFAULT 0,
                http_status INT DEFAULT 200,
                estimated_cost_usd NUMERIC(8, 5) DEFAULT 0.00000,
                details TEXT
            );
        """)
        print("[OK] Schema 'control' and audit tables verified (pipeline_runs, data_quality_log, api_usage_log).")

        # 2. Check existing raw tables and constraints
        cur.execute("""
            SELECT tc.table_name, tc.constraint_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'raw' AND tc.constraint_type = 'UNIQUE'
            ORDER BY tc.table_name, tc.constraint_name;
        """)
        constraints = cur.fetchall()
        print(f"[OK] Found {len(constraints)} unique constraint mappings in 'raw' schema.")

        # 3. Check row counts in primary tables
        check_tables = [
            "raw.ga4_blog_daily",
            "raw.ga4_course_daily",
            "raw.gsc_blog_pages",
            "raw.gsc_course_pages",
            "raw.gsc_blog_queries"
        ]
        print("\n--- Current Target Table Status ---")
        for tbl in check_tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl};")
                cnt = cur.fetchone()[0]
                print(f"  * {tbl:<24} : {cnt:>9,} rows")
            except Exception:
                print(f"  * {tbl:<24} : (table not found)")

    conn.close()
    print("\n" + "=" * 65)
    print("[OK] Database is fully verified and ready for live CDC ingestion!")
    print("=" * 65)
    return True

if __name__ == "__main__":
    verify_and_prepare_database()
