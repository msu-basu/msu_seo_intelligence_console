"""
ai_summary.py
Executive summary generator supporting both deterministic calculations and AI LLM synthesis.
"""
from typing import Dict, Any, Optional

def generate_deterministic_summary(summary_data: Dict[str, Any]) -> str:
    """Generates an executive textual summary based strictly on loaded metrics without external AI calls."""
    sessions = summary_data.get("sessions", 0)
    views = summary_data.get("views", 0)
    leads = summary_data.get("key_events", 0)
    clicks = summary_data.get("gsc_clicks", 0)
    impressions = summary_data.get("gsc_impressions", 0)
    ctr = summary_data.get("gsc_ctr", 0.0)
    
    if sessions == 0 and views == 0 and clicks == 0:
        return "⚠️ Insufficient data loaded to generate an analytical summary. Please ensure data is loaded in PostgreSQL or `data/input/`."
        
    text = f"""
    ### Executive Analytical Highlights (MSU Web Analytics)
    
    1. **Traffic & User Engagement:** The portal captured **{sessions:,} total sessions** and **{views:,} page views** across academic and blog content.
    2. **Lead Conversions:** A total of **{leads:,} Key Events (Lead Form Success)** were recorded during this reporting window.
    3. **Search Engine Visibility:** Google Search Console recorded **{clicks:,} organic search clicks** and **{impressions:,} total impressions** (Average CTR: **{ctr:.2f}%**).
    """
    return text.strip()


def generate_ai_executive_summary(
    summary_data: Dict[str, Any],
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generates an executive textual summary using the configured AI client.
    Falls back gracefully to generate_deterministic_summary if AI is unavailable.
    """
    from src.ai.client import AIClient
    
    client = AIClient(provider=provider, api_key=api_key, model=model)
    if not client.has_valid_credentials() or client.provider == "local":
        return generate_deterministic_summary(summary_data)

    prompt = f"""
Given the following key performance indicators for Medhavi Skills University (MSU):
- Total Sessions: {summary_data.get('sessions', 0):,}
- Total Page Views: {summary_data.get('views', 0):,}
- Total Key Events (Admission Leads): {summary_data.get('key_events', 0):,}
- Organic Google Search Clicks: {summary_data.get('gsc_clicks', 0):,}
- Total Search Impressions: {summary_data.get('gsc_impressions', 0):,}
- Search Click-Through Rate: {summary_data.get('gsc_ctr', 0.0):.2f}%

Synthesize a concise 3-paragraph executive brief highlighting traffic performance, lead acquisition efficiency, and high-impact SEO opportunities.
"""
    try:
        response = client.generate_chat_response(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are a senior SEO and digital marketing executive consultant.",
            temperature=0.3,
            max_tokens=600
        )
        return response
    except Exception:
        return generate_deterministic_summary(summary_data)
