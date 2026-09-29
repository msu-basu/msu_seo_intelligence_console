import pytest
import psycopg

DB_URL = "postgresql://postgres:123@localhost:5432/web_analytics"

def test_control_schema_and_tables_exist():
    """Verify that control.pipeline_runs and control.data_quality_log exist."""
    conn = psycopg.connect(DB_URL)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'control';
        """)
        tables = [r[0] for r in cur.fetchall()]
        assert "pipeline_runs" in tables, "control.pipeline_runs table missing"
        assert "data_quality_log" in tables, "control.data_quality_log table missing"
    conn.close()

def test_natural_unique_constraints_exist():
    """Verify that natural composite unique keys are enforced on all raw tables."""
    conn = psycopg.connect(DB_URL)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT conname 
            FROM pg_constraint 
            WHERE connamespace = 'raw'::regnamespace AND contype = 'u';
        """)
        constraints = [r[0] for r in cur.fetchall()]
        
        expected_constraints = [
            "uq_ga4_blog_daily",
            "uq_ga4_course_daily",
            "uq_ga4_device",
            "uq_ga4_events",
            "uq_ga4_geo_global",
            "uq_ga4_geo_city_device",
            "uq_ga4_overall_baseline",
            "uq_gsc_blog_pages",
            "uq_gsc_course_pages",
            "uq_gsc_blog_countries",
            "uq_gsc_course_countries",
            "uq_gsc_blog_devices",
            "uq_gsc_course_devices",
            "uq_gsc_blog_queries",
            "uq_gsc_course_queries",
        ]
        
        for c in expected_constraints:
            assert c in constraints, f"Missing unique constraint: {c}"
    conn.close()

def test_idempotent_upsert_simulation():
    """Simulate running ingestion twice for the same record to verify 0 duplicates."""
    conn = psycopg.connect(DB_URL, autocommit=True)
    test_path = "/blog/test-idempotency-article"
    test_date = "2026-09-28"
    
    with conn.cursor() as cur:
        cur.execute("DELETE FROM raw.ga4_blog_daily WHERE page_path = %s;", (test_path,))
        
        upsert_query = """
            INSERT INTO raw.ga4_blog_daily (page_path, report_date, views, active_users)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (page_path, report_date)
            DO UPDATE SET 
                views = EXCLUDED.views,
                active_users = EXCLUDED.active_users,
                loaded_at = NOW();
        """
        cur.execute(upsert_query, (test_path, test_date, 100, 50))
        
        cur.execute("SELECT views, active_users FROM raw.ga4_blog_daily WHERE page_path = %s AND report_date = %s;", (test_path, test_date))
        row = cur.fetchone()
        assert row == (100, 50), "First insertion failed"
        
        # Second run: Same natural key with updated data
        cur.execute(upsert_query, (test_path, test_date, 150, 75))
        
        cur.execute("SELECT COUNT(*), views, active_users FROM raw.ga4_blog_daily WHERE page_path = %s AND report_date = %s GROUP BY views, active_users;", (test_path, test_date))
        rows = cur.fetchall()
        
        assert len(rows) == 1, "Duplicate row created on re-run!"
        assert rows[0][0] == 1, "Multiple records exist for the same natural key!"
        assert rows[0][1] == 150, "Views was not updated during idempotent upsert!"
        assert rows[0][2] == 75, "Active users was not updated during idempotent upsert!"
        
        cur.execute("DELETE FROM raw.ga4_blog_daily WHERE page_path = %s;", (test_path,))
    conn.close()
