"""
test_google_auth.py
Verification script for Google Analytics 4 and Google Search Console API credentials.
Run: python scripts/test_google_auth.py
"""
import os
import sys
from pathlib import Path
from datetime import date, timedelta

# Try importing Google API client libraries
try:
    from google.oauth2 import service_account
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric
    from googleapiclient.discovery import build
except ImportError as e:
    print("[ERROR] Missing Google Cloud client libraries: " + str(e))
    print("Run: pip install google-analytics-data google-api-python-client google-auth")
    sys.exit(1)

# Try loading dotenv if present
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    else:
        load_dotenv()
except ImportError:
    pass

CRED_PATH_RAW = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials/google_service_account.json")
# Resolve relative paths relative to project root
if not os.path.isabs(CRED_PATH_RAW):
    project_root = Path(__file__).resolve().parent.parent
    CRED_PATH = str((project_root / CRED_PATH_RAW).resolve())
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.pipeline.auth import get_google_credentials

GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "").strip()
GSC_SITE_URL = os.getenv("GSC_SITE_URL", "").strip()

def check_credentials_file():
    print("=" * 65)
    print("1. Checking Service Account Credentials Mode")
    print("=" * 65)
    if os.getenv("GOOGLE_CREDENTIALS_BASE64"):
        print("[OK] Production Mode Detected: GOOGLE_CREDENTIALS_BASE64 found in RAM.")
        print("     Zero physical credential files required on disk!\n")
        return True

    p = Path(CRED_PATH)
    if not p.exists():
        print(f"[ERROR] Credentials NOT found.")
        print("  Either provide GOOGLE_CREDENTIALS_BASE64 in your environment,")
        print(f"  or place your service account JSON file at: {p}\n")
        return False
    print(f"[OK] Local Dev Mode: Credentials file found: {p}\n")
    return True

def test_ga4():
    print("=" * 65)
    print("2. Testing Google Analytics 4 (GA4) Data API Connection")
    print("=" * 65)
    if not GA4_PROPERTY_ID or GA4_PROPERTY_ID == "123456789":
        print("[WARNING] GA4_PROPERTY_ID is not configured in .env.")
        print("  Find your Property ID in: GA4 Admin -> Property Settings -> Property Details.")
        print("  Then set GA4_PROPERTY_ID=<numeric_id> in .env and re-run.\n")
        return False

    try:
        credentials = get_google_credentials(
            scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        client = BetaAnalyticsDataClient(credentials=credentials)

        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
            metrics=[Metric(name="activeUsers")],
        )
        response = client.run_report(request)

        users = response.rows[0].metric_values[0].value if response.rows else "0"
        print("[OK] GA4 Connection SUCCESSFUL!")
        print(f"     Property ID: {GA4_PROPERTY_ID}")
        print(f"     Active Users (last 7 days): {users}\n")
        return True
    except Exception as e:
        print("[ERROR] GA4 Connection Failed:")
        print(f"  {e}\n")
        print("  Common causes:")
        print("  1. Service account email is not added as a Viewer in GA4 Property Access Management.")
        print("  2. Google Analytics Data API is not enabled in your Google Cloud Console project.")
        print('  3. Property ID is invalid or formatted with "properties/".\n')
        return False

def test_gsc():
    print("=" * 65)
    print("3. Testing Google Search Console (GSC) API Connection")
    print("=" * 65)
    if not GSC_SITE_URL:
        print("[WARNING] GSC_SITE_URL is not configured in .env.")
        print("  Set GSC_SITE_URL=https://www.msu.edu.in/ (or sc-domain:msu.edu.in) in .env and re-run.\n")
        return False

    try:
        credentials = get_google_credentials(
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        service = build("searchconsole", "v1", credentials=credentials)

        # GSC data typically has a 2-3 day latency; test with a 3-day window from 5 days ago
        end_d = date.today() - timedelta(days=3)
        start_d = date.today() - timedelta(days=6)

        request = {
            "startDate": start_d.strftime("%Y-%m-%d"),
            "endDate": end_d.strftime("%Y-%m-%d"),
            "rowLimit": 5
        }
        response = service.searchanalytics().query(siteUrl=GSC_SITE_URL, body=request).execute()

        rows = response.get("rows", [])
        print("[OK] GSC Connection SUCCESSFUL!")
        print(f"     Site URL: {GSC_SITE_URL}")
        print(f"     Sample rows returned: {len(rows)}")
        if rows:
            print(f'     Sample query: {rows[0].get("keys", ["N/A"])}')
            print(f'     Sample clicks: {rows[0].get("clicks", 0)}, impressions: {rows[0].get("impressions", 0)}')
        print("")
        return True
    except Exception as e:
        print("[ERROR] GSC Connection Failed:")
        print(f"  {e}\n")
        print("  Common causes:")
        print("  1. Service account email is not added as a user in GSC (Settings -> Users & Permissions).")
        print("  2. Google Search Console API is not enabled in your Google Cloud Console project.")
        print("  3. Site URL format does not match exactly (e.g., https://www.msu.edu.in/ vs sc-domain:msu.edu.in).\n")
        return False

if __name__ == "__main__":
    print("\n>>> Running Google API Authentication Preflight Check...\n")
    creds_ok = check_credentials_file()
    if creds_ok:
        test_ga4()
        test_gsc()
    print("=" * 65)
    print("Preflight Check Complete.")
    print("=" * 65)
