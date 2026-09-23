from typing import Dict, Any

def generate_deterministic_summary(summary_data: Dict[str, Any]) -> str:
    """Generates an executive textual summary based strictly on loaded metrics without external AI calls."""
    sessions = summary_data.get("sessions", 0)
    views = summary_data.get("views", 0)
    leads = summary_data.get("key_events", 0)
    clicks = summary_data.get("gsc_clicks", 0)
    
    if sessions == 0 and views == 0 and clicks == 0:
        return "⚠️ Insufficient data loaded to generate an analytical summary. Please ensure CSV exports are placed in `data/input/`."
        
    text = f"""
    ### Executive Analytical Highlights (Jan 1, 2026 – Sep 21, 2026)
    
    1. **Traffic & User Engagement:** The portal captured **{sessions:,} total sessions** and **{views:,} page views** across academic and blog content.
    2. **Lead Conversions:** A total of **{leads:,} Key Events (Lead Form Success)** were recorded during this reporting window.
    3. **Search Engine Visibility:** Google Search Console recorded **{clicks:,} organic search clicks** and **{summary_data.get('gsc_impressions', 0):,} total impressions**.
    """
    return text