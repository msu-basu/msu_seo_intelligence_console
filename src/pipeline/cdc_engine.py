"""
cdc_engine.py
Change Data Capture (CDC) and Dual-Target Storage Engine:
1. PostgreSQL Idempotent Upserts: Exact-once writes into existing production raw tables.
2. File Staging / Baseline Sync: Exports to local CSV/Parquet in data/staging/ for verification.
3. Modular toggle: Set PIPELINE_EXPORT_FILES=False to cleanly disable Excel/file writes.
"""
import os
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple
import pandas as pd
import psycopg
from dotenv import load_dotenv

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

EXPORT_FILES_DEFAULT = os.getenv("PIPELINE_EXPORT_FILES", "true").lower() in ("true", "1", "yes")

class CDCEngine:
    def __init__(self, export_files: bool = EXPORT_FILES_DEFAULT):
        self.export_files = export_files
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.staging_dir = self.project_root / "data" / "staging"
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def get_db_connection(self):
        return psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True
        )

    def get_max_extracted_date(self) -> Optional[date]:
        """Queries database to find the latest extracted report_date (high-watermark)."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(report_date) FROM raw.ga4_blog_daily;")
                row = cur.fetchone()
                max_date = row[0] if row and row[0] else None
            conn.close()
            return max_date
        except Exception as e:
            print(f"[WARN] Could not retrieve max extracted date: {e}")
            return None

    def get_max_parquet_date(self) -> Optional[date]:
        """Queries local processed parquet files to find latest Date present."""
        try:
            blog_pq = self.project_root / "data" / "processed" / "01_Blog_GA4.parquet"
            if blog_pq.exists():
                df = pd.read_parquet(blog_pq, columns=["Date"])
                s = pd.to_datetime(df["Date"], errors="coerce").dropna()
                if not s.empty:
                    return s.max().date()
        except Exception as e:
            print(f"[WARN] Could not retrieve max parquet date: {e}")
        return None

    def log_pipeline_start(self, job_name: str, source: str, start_date: str, end_date: str) -> Optional[str]:
        """Logs start of run to control.pipeline_runs using production schema."""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO control.pipeline_runs 
                        (source, report_name, job_mode, start_date, end_date, status, started_at)
                    VALUES (%s, %s, 'CDC_INCREMENTAL', %s, %s, 'RUNNING', NOW())
                    RETURNING pipeline_run_id;
                """, (source, job_name, start_date, end_date))
                run_id = str(cur.fetchone()[0])
            conn.close()
            return run_id
        except Exception as e:
            print(f"[WARN] Database control logging skipped: {e}")
            return None

    def log_pipeline_complete(
        self,
        run_id: Optional[str],
        status: str,
        extracted: int,
        upserted: int,
        error_msg: Optional[str] = None
    ):
        """Updates pipeline run completion status in control.pipeline_runs."""
        if not run_id:
            return
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE control.pipeline_runs
                    SET status = %s,
                        rows_extracted = %s,
                        rows_upserted = %s,
                        completed_at = NOW(),
                        error_message = %s
                    WHERE pipeline_run_id = %s;
                """, (status, extracted, upserted, error_msg, run_id))
            conn.close()
        except Exception as e:
            print(f"[WARN] Failed to update pipeline run status: {e}")

    def log_api_calls(self, run_id: Optional[str], call_logs: list):
        """Logs individual API hit durations, request counts, and cost metrics into control.api_usage_log."""
        if not run_id or not call_logs:
            return
        sql = """
            INSERT INTO control.api_usage_log 
                (pipeline_run_id, api_service, endpoint_method, target_metric, duration_ms, rows_returned, http_status, estimated_cost_usd, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        records = [
            (
                run_id,
                c["api_service"],
                c["endpoint_method"],
                c.get("target_metric", ""),
                int(c["duration_ms"]),
                int(c.get("rows_returned", 0)),
                int(c.get("http_status", 200)),
                0.00000,
                c.get("details", "")
            )
            for c in call_logs
        ]
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
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
                cur.executemany(sql, records)
            conn.close()
        except Exception as e:
            print(f"[WARN] Failed to write API call logs: {e}")

    def upsert_ga4_daily(self, df: pd.DataFrame, table_name: str = "raw.ga4_blog_daily") -> int:
        """CDC Upsert into raw.ga4_blog_daily or raw.ga4_course_daily."""
        if df.empty:
            return 0
            
        sql = f"""
            INSERT INTO {table_name} 
                (page_path, report_date, views, active_users)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (page_path, report_date) DO UPDATE SET
                views = EXCLUDED.views,
                active_users = EXCLUDED.active_users;
        """
        records = [
            (r["page_path"], r["report_date"], int(r["views"]), int(r["active_users"]))
            for _, r in df.iterrows()
        ]
        
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.executemany(sql, records)
            conn.close()
            return len(records)
        except Exception as e:
            print(f"[DB ERROR] Upsert failed for {table_name}: {e}")
            raise e

    def upsert_gsc_pages(self, df: pd.DataFrame, table_name: str = "raw.gsc_blog_pages") -> int:
        """CDC Upsert into raw.gsc_blog_pages or raw.gsc_course_pages using page_url key."""
        if df.empty:
            return 0
            
        sql = f"""
            INSERT INTO {table_name}
                (page_url, clicks, impressions, ctr, position)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (page_url) DO UPDATE SET
                clicks = EXCLUDED.clicks,
                impressions = EXCLUDED.impressions,
                ctr = EXCLUDED.ctr,
                position = EXCLUDED.position;
        """
        records = [
            (
                r.get("page_url", r.get("page_path")),
                int(r["clicks"]),
                int(r["impressions"]),
                float(r["ctr"]),
                float(r["position"])
            )
            for _, r in df.iterrows()
        ]
        
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.executemany(sql, records)
            conn.close()
            return len(records)
        except Exception as e:
            print(f"[DB ERROR] Upsert failed for {table_name}: {e}")
            raise e

    def upsert_gsc_queries(self, df: pd.DataFrame, table_name: str = "raw.gsc_blog_queries") -> int:
        """CDC Upsert into raw.gsc_blog_queries or raw.gsc_course_queries using query key."""
        if df.empty:
            return 0
            
        sql = f"""
            INSERT INTO {table_name}
                (query, clicks, impressions, ctr, position)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (query) DO UPDATE SET
                clicks = EXCLUDED.clicks,
                impressions = EXCLUDED.impressions,
                ctr = EXCLUDED.ctr,
                position = EXCLUDED.position;
        """
        records = [
            (
                r["query"],
                int(r["clicks"]),
                int(r["impressions"]),
                float(r["ctr"]),
                float(r["position"])
            )
            for _, r in df.iterrows()
        ]
        
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.executemany(sql, records)
            conn.close()
            return len(records)
        except Exception as e:
            print(f"[DB ERROR] Upsert failed for {table_name}: {e}")
            raise e

    def stage_to_files(self, df: pd.DataFrame, filename_base: str):
        """
        Saves fresh snapshot to data/staging/ as CSV and Parquet for visual inspection.
        Can be disabled by setting export_files=False.
        """
        if not self.export_files or df.empty:
            return
            
        csv_path = self.staging_dir / f"{filename_base}.csv"
        parquet_path = self.staging_dir / f"{filename_base}.parquet"
        
        df.to_csv(csv_path, index=False, encoding="utf-8")
        try:
            df.to_parquet(parquet_path, index=False)
        except Exception:
            pass
        print(f"  [STAGING FILE] Saved {len(df):,} rows -> data/staging/{csv_path.name}")

    def sync_to_processed_parquet(self, df_blog: pd.DataFrame, df_course: pd.DataFrame):
        """
        Merges newly ingested daily records into data/processed/*.parquet
        so the Streamlit dashboard immediately displays the fresh dates and KPIs.
        """
        processed_dir = self.project_root / "data" / "processed"
        if not processed_dir.exists():
            return

        # 1. Update 01_Blog_GA4.parquet
        blog_pq = processed_dir / "01_Blog_GA4.parquet"
        if blog_pq.exists() and not df_blog.empty:
            df_old = pd.read_parquet(blog_pq)
            df_old["Date"] = pd.to_datetime(df_old["Date"], errors="coerce")

            df_new = pd.DataFrame()
            df_new["Page path and screen class"] = df_blog["page_path"]
            df_new["Views"] = df_blog["views"].astype(int)
            df_new["Bounce rate"] = df_blog["bounce_rate"].astype(float)
            df_new["Active users"] = df_blog["active_users"].astype(int)
            df_new["Views per active user"] = (df_blog["views"] / df_blog["active_users"].replace(0, 1)).round(2)
            df_new["Average engagement time per active user"] = df_blog["avg_engagement_time"].astype(float)
            df_new["Event count"] = df_blog["event_count"].astype(int)
            df_new["Key events"] = 0
            df_new["Total revenue"] = 0
            df_new["Date"] = pd.to_datetime(df_blog["report_date"], errors="coerce")

            merged = pd.concat([df_old, df_new], ignore_index=True)
            merged = merged.drop_duplicates(subset=["Page path and screen class", "Date"], keep="last")
            merged.to_parquet(blog_pq, index=False)
            new_max = merged["Date"].max().strftime("%Y-%m-%d")
            print(f"  [STREAMLIT PARQUET SYNC] 01_Blog_GA4.parquet updated -> New Max Date: {new_max} ({len(merged):,} rows)")

        # 2. Update 02_Course_GA4.parquet
        course_pq = processed_dir / "02_Course_GA4.parquet"
        if course_pq.exists() and not df_course.empty:
            df_old = pd.read_parquet(course_pq)
            df_old["Date"] = pd.to_datetime(df_old["Date"], errors="coerce")

            df_new = pd.DataFrame()
            df_new["Page path and screen class"] = df_course["page_path"]
            df_new["Views"] = df_course["views"].astype(int)
            df_new["Bounce rate"] = df_course["bounce_rate"].astype(float)
            df_new["Active users"] = df_course["active_users"].astype(int)
            df_new["Views per active user"] = (df_course["views"] / df_course["active_users"].replace(0, 1)).round(2)
            df_new["Average engagement time per active user"] = df_course["avg_engagement_time"].astype(float)
            df_new["Event count"] = df_course["event_count"].astype(int)
            df_new["Key events"] = 0
            df_new["Total revenue"] = 0
            df_new["Date"] = pd.to_datetime(df_course["report_date"], errors="coerce")

            merged = pd.concat([df_old, df_new], ignore_index=True)
            merged = merged.drop_duplicates(subset=["Page path and screen class", "Date"], keep="last")
            merged.to_parquet(course_pq, index=False)
            new_max = merged["Date"].max().strftime("%Y-%m-%d")
            print(f"  [STREAMLIT PARQUET SYNC] 02_Course_GA4.parquet updated -> New Max Date: {new_max} ({len(merged):,} rows)")

