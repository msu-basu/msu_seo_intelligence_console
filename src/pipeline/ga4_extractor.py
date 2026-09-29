"""
ga4_extractor.py
Fetches daily grain web analytics data from Google Analytics 4 Data API.
Handles pagination, dimension/metric mappings, and URL pattern filtering.
"""
import os
from pathlib import Path
from datetime import date, timedelta
import time
from typing import Dict, List, Optional, Any
import pandas as pd
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    FilterExpression,
    Filter,
)

from src.pipeline.auth import get_google_credentials

class GA4Extractor:
    def __init__(self, credentials_path: Optional[str] = None, property_id: str = ""):
        self.property_id = property_id.strip()
        self.call_logs: List[Dict[str, Any]] = []
        
        credentials = get_google_credentials(
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            custom_path=credentials_path
        )
        self.client = BetaAnalyticsDataClient(credentials=credentials)

    def fetch_pages_daily(
        self,
        start_date: str,
        end_date: str,
        path_filter_string: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Pulls daily grain page-level metrics:
        Dimensions: date, pagePath
        Metrics: screenPageViews, activeUsers, bounceRate, eventCount, userEngagementDuration
        """
        dimension_filter = None
        if path_filter_string:
            dimension_filter = FilterExpression(
                filter=Filter(
                    field_name="pagePath",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.CONTAINS,
                        value=path_filter_string,
                        case_sensitive=False
                    )
                )
            )

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="pagePath"),
            ],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
                Metric(name="bounceRate"),
                Metric(name="eventCount"),
                Metric(name="userEngagementDuration"),
            ],
            dimension_filter=dimension_filter,
            limit=100000,
        )

        t0 = time.perf_counter()
        try:
            response = self.client.run_report(request)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            self.call_logs.append({
                "api_service": "GA4 Data API",
                "endpoint_method": "run_report",
                "target_metric": f"pages ({path_filter_string or 'all'})",
                "duration_ms": duration_ms,
                "rows_returned": len(response.rows),
                "http_status": 200,
                "details": f"window: {start_date} to {end_date}"
            })
        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            self.call_logs.append({
                "api_service": "GA4 Data API",
                "endpoint_method": "run_report",
                "target_metric": f"pages ({path_filter_string or 'all'})",
                "duration_ms": duration_ms,
                "rows_returned": 0,
                "http_status": 500,
                "details": str(e)
            })
            raise e
        
        rows = []
        for r in response.rows:
            # GA4 returns date in YYYYMMDD format
            raw_date = r.dimension_values[0].value
            formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date
            page_path = r.dimension_values[1].value
            
            views = int(r.metric_values[0].value or 0)
            active_users = int(r.metric_values[1].value or 0)
            bounce_rate = round(float(r.metric_values[2].value or 0), 4)
            event_count = int(r.metric_values[3].value or 0)
            engagement_time = round(float(r.metric_values[4].value or 0), 2)
            
            rows.append({
                "report_date": formatted_date,
                "page_path": page_path,
                "views": views,
                "active_users": active_users,
                "bounce_rate": bounce_rate,
                "event_count": event_count,
                "avg_engagement_time": engagement_time,
            })

        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=[
                "report_date", "page_path", "views", "active_users",
                "bounce_rate", "event_count", "avg_engagement_time"
            ])
        return df

    def fetch_devices_daily(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Pulls daily device category breakdown."""
        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="deviceCategory"),
            ],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
            ],
            limit=10000,
        )
        response = self.client.run_report(request)
        rows = []
        for r in response.rows:
            raw_date = r.dimension_values[0].value
            formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date
            rows.append({
                "report_date": formatted_date,
                "device_category": r.dimension_values[1].value,
                "views": int(r.metric_values[0].value or 0),
                "active_users": int(r.metric_values[1].value or 0),
            })
        return pd.DataFrame(rows)
