"""
create_views.py
Creates optimized analytical SQL views in PostgreSQL under the 'analytics' schema.
These pre-aggregated views allow Streamlit to retrieve sub-second summary metrics
without transferring hundreds of thousands of raw daily rows over the network.
"""
import os
from pathlib import Path
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


def create_analytics_views():
    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True
    )

    with conn.cursor() as cur:
        print("[*] Creating analytics schema and indexes...")
        cur.execute("CREATE SCHEMA IF NOT EXISTS analytics;")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_ga4_course_daily_date ON raw.ga4_course_daily (report_date);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_ga4_blog_daily_date ON raw.ga4_blog_daily (report_date);")

        # 1. Blog Page-Level Summary View (~540 rows instead of 196k)
        print("[*] Creating analytics.v_blog_page_summary...")
        cur.execute("""
            CREATE OR REPLACE VIEW analytics.v_blog_page_summary AS
            SELECT 
                page_path AS "Page path and screen class",
                COALESCE(SUM(views), 0)::BIGINT AS "Views",
                COALESCE(MAX(active_users), 0)::BIGINT AS "Active users",
                COALESCE(SUM(event_count), 0)::BIGINT AS "Event count",
                COALESCE(SUM(key_events), 0)::BIGINT AS "Key events",
                ROUND(AVG(bounce_rate)::numeric, 4) AS "Bounce rate",
                ROUND(AVG(avg_engagement_time_per_active_user)::numeric, 2) AS "Average engagement time per active user"
            FROM raw.ga4_blog_daily
            WHERE page_path NOT IN ('/blog', '/blog/', '/', '(not set)', '')
            GROUP BY page_path;
        """)

        # 2. Course Page-Level Summary View (~160 rows instead of 60k)
        print("[*] Creating analytics.v_course_page_summary...")
        cur.execute("""
            CREATE OR REPLACE VIEW analytics.v_course_page_summary AS
            SELECT 
                page_path AS "Page path and screen class",
                COALESCE(SUM(views), 0)::BIGINT AS "Views",
                COALESCE(MAX(active_users), 0)::BIGINT AS "Active users",
                COALESCE(SUM(event_count), 0)::BIGINT AS "Event count",
                COALESCE(SUM(key_events), 0)::BIGINT AS "Key events",
                ROUND(AVG(bounce_rate)::numeric, 4) AS "Bounce rate",
                ROUND(AVG(avg_engagement_time_per_active_user)::numeric, 2) AS "Average engagement time per active user"
            FROM raw.ga4_course_daily
            WHERE page_path NOT IN ('/', '/courses', '/courses/', '(not set)', '')
              AND page_path ILIKE '%/course%'
            GROUP BY page_path;
        """)

        # 3. Daily Traffic Trends View (~730 rows instead of 260k)
        print("[*] Creating analytics.v_daily_traffic_trends...")
        cur.execute("""
            CREATE OR REPLACE VIEW analytics.v_daily_traffic_trends AS
            SELECT 
                report_date AS "Date",
                'Blog' AS "Channel",
                COALESCE(SUM(views), 0)::BIGINT AS "Views",
                COALESCE(SUM(active_users), 0)::BIGINT AS "Active users"
            FROM raw.ga4_blog_daily
            GROUP BY report_date
            UNION ALL
            SELECT 
                report_date AS "Date",
                'Courses' AS "Channel",
                COALESCE(SUM(views), 0)::BIGINT AS "Views",
                COALESCE(SUM(active_users), 0)::BIGINT AS "Active users"
            FROM raw.ga4_course_daily
            GROUP BY report_date
            ORDER BY "Date" ASC, "Channel" ASC;
        """)

        # 4. GSC Unified Queries View
        print("[*] Creating analytics.v_gsc_top_queries...")
        cur.execute("""
            CREATE OR REPLACE VIEW analytics.v_gsc_top_queries AS
            SELECT 
                query AS "Top queries",
                clicks AS "Clicks",
                impressions AS "Impressions",
                ctr AS "CTR",
                position AS "Position",
                'Blog' AS "Channel"
            FROM raw.gsc_blog_queries
            UNION ALL
            SELECT 
                query AS "Top queries",
                clicks AS "Clicks",
                impressions AS "Impressions",
                ctr AS "CTR",
                position AS "Position",
                'Course' AS "Channel"
            FROM raw.gsc_course_queries;
        """)

        print("[OK] All PostgreSQL aggregation views created successfully!")
    conn.close()


if __name__ == "__main__":
    create_analytics_views()
