"""
gsc_extractor.py
Fetches daily search performance metrics from Google Search Console API.
Extracts clicks, impressions, CTR, and average position partitioned by page, query, and date.
"""
import os
from pathlib import Path
from datetime import date, timedelta
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.pipeline.auth import get_google_credentials

class GSCExtractor:
    def __init__(self, credentials_path: Optional[str] = None, site_url: str = ""):
        self.site_url = site_url.strip()
        self.call_logs: List[Dict[str, Any]] = []
        
        credentials = get_google_credentials(
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
            custom_path=credentials_path
        )
        self.service = build("searchconsole", "v1", credentials=credentials)

    def fetch_pages_daily(
        self,
        start_date: str,
        end_date: str,
        path_filter_string: Optional[str] = None,
        row_limit: int = 25000
    ) -> pd.DataFrame:
        """
        Pulls daily search performance aggregated by page.
        Dimensions: date, page
        """
        request_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["date", "page"],
            "rowLimit": row_limit,
            "dataState": "all"
        }

        if path_filter_string:
            request_body["dimensionFilterGroups"] = [{
                "filters": [{
                    "dimension": "page",
                    "operator": "contains",
                    "expression": path_filter_string
                }]
            }]

        t0 = time.perf_counter()
        try:
            response = self.service.searchanalytics().query(
                siteUrl=self.site_url,
                body=request_body
            ).execute()
            duration_ms = int((time.perf_counter() - t0) * 1000)
            rows_count = len(response.get("rows", []))
            self.call_logs.append({
                "api_service": "Google Search Console API",
                "endpoint_method": "searchanalytics.query (pages)",
                "target_metric": f"pages ({path_filter_string or 'all'})",
                "duration_ms": duration_ms,
                "rows_returned": rows_count,
                "http_status": 200,
                "details": f"window: {start_date} to {end_date}"
            })
        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            self.call_logs.append({
                "api_service": "Google Search Console API",
                "endpoint_method": "searchanalytics.query (pages)",
                "target_metric": f"pages ({path_filter_string or 'all'})",
                "duration_ms": duration_ms,
                "rows_returned": 0,
                "http_status": 500,
                "details": str(e)
            })
            print(f"[GSC ERROR] Failed to fetch page data: {e}")
            return pd.DataFrame()

        rows = []
        for r in response.get("rows", []):
            keys = r.get("keys", [])
            report_date = keys[0] if len(keys) > 0 else ""
            full_url = keys[1] if len(keys) > 1 else ""
            
            # Normalize to relative path for joining with GA4
            parsed = urlparse(full_url)
            page_path = parsed.path or full_url
            if parsed.query:
                page_path = f"{page_path}?{parsed.query}"

            clicks = int(r.get("clicks", 0))
            impressions = int(r.get("impressions", 0))
            ctr = round(float(r.get("ctr", 0.0)), 4)
            pos = round(float(r.get("position", 0.0)), 2)

            rows.append({
                "report_date": report_date,
                "page_url": full_url,
                "page_path": page_path,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": ctr,
                "position": pos,
            })

        return pd.DataFrame(rows)

    def fetch_queries_daily(
        self,
        start_date: str,
        end_date: str,
        path_filter_string: Optional[str] = None,
        row_limit: int = 25000
    ) -> pd.DataFrame:
        """
        Pulls search query/keyword performance.
        Dimensions: date, query, page
        """
        request_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["date", "query", "page"],
            "rowLimit": row_limit,
            "dataState": "all"
        }

        if path_filter_string:
            request_body["dimensionFilterGroups"] = [{
                "filters": [{
                    "dimension": "page",
                    "operator": "contains",
                    "expression": path_filter_string
                }]
            }]

        t0 = time.perf_counter()
        try:
            response = self.service.searchanalytics().query(
                siteUrl=self.site_url,
                body=request_body
            ).execute()
            duration_ms = int((time.perf_counter() - t0) * 1000)
            rows_count = len(response.get("rows", []))
            self.call_logs.append({
                "api_service": "Google Search Console API",
                "endpoint_method": "searchanalytics.query (queries)",
                "target_metric": f"queries ({path_filter_string or 'all'})",
                "duration_ms": duration_ms,
                "rows_returned": rows_count,
                "http_status": 200,
                "details": f"window: {start_date} to {end_date}"
            })
        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            self.call_logs.append({
                "api_service": "Google Search Console API",
                "endpoint_method": "searchanalytics.query (queries)",
                "target_metric": f"queries ({path_filter_string or 'all'})",
                "duration_ms": duration_ms,
                "rows_returned": 0,
                "http_status": 500,
                "details": str(e)
            })
            print(f"[GSC ERROR] Failed to fetch queries: {e}")
            return pd.DataFrame()

        rows = []
        for r in response.get("rows", []):
            keys = r.get("keys", [])
            report_date = keys[0] if len(keys) > 0 else ""
            query = keys[1] if len(keys) > 1 else ""
            full_url = keys[2] if len(keys) > 2 else ""

            parsed = urlparse(full_url)
            page_path = parsed.path or full_url

            rows.append({
                "report_date": report_date,
                "query": query,
                "page_path": page_path,
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "ctr": round(float(r.get("ctr", 0.0)), 4),
                "position": round(float(r.get("position", 0.0)), 2),
            })

        return pd.DataFrame(rows)
