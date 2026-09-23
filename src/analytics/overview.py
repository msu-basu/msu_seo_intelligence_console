import pandas as pd
from typing import Dict, Any

def get_executive_summary(datasets: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Calculates global KPIs across all loaded datasets."""
    summary = {
        "sessions": 0,
        "users": 0,
        "views": 0,
        "engagement_rate": 0.0,
        "key_events": 0,
        "gsc_clicks": 0,
        "gsc_impressions": 0,
        "gsc_ctr": 0.0
    }
    
    if "overall" in datasets and not datasets["overall"].empty:
        df = datasets["overall"]
        summary["sessions"] = int(df.get("Sessions", pd.Series([0])).sum())
        summary["key_events"] = int(df.get("Key events", pd.Series([0])).sum())
        if "Engagement rate" in df.columns:
            summary["engagement_rate"] = float(df["Engagement rate"].mean() * 100)
            
    if "blog" in datasets and not datasets["blog"].empty:
        summary["views"] += int(datasets["blog"].get("Views", pd.Series([0])).sum())
        summary["users"] += int(datasets["blog"].get("Active users", pd.Series([0])).sum())
        
    if "course" in datasets and not datasets["course"].empty:
        summary["views"] += int(datasets["course"].get("Views", pd.Series([0])).sum())
        summary["users"] += int(datasets["course"].get("Active users", pd.Series([0])).sum())
        
    if "gsc_queries" in datasets and not datasets["gsc_queries"].empty:
        df = datasets["gsc_queries"]
        summary["gsc_clicks"] = int(df.get("Clicks", pd.Series([0])).sum())
        summary["gsc_impressions"] = int(df.get("Impressions", pd.Series([0])).sum())
        if summary["gsc_impressions"] > 0:
            summary["gsc_ctr"] = (summary["gsc_clicks"] / summary["gsc_impressions"]) * 100
            
    return summary