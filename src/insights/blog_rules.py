import pandas as pd
from typing import Dict, Optional

def detect_seo_opportunities(
    blog_df: Optional[pd.DataFrame] = None, 
    gsc_df: Optional[pd.DataFrame] = None,
    thresholds: Optional[Dict] = None
) -> Dict[str, pd.DataFrame]:
    """Rule-based engine detecting traffic/lead gaps and search bottlenecks."""
    if thresholds is None:
        thresholds = {"traffic_percentile": 0.75, "weak_position": 20, "low_ctr": 2.0}
        
    if blog_df is None:
        blog_df = pd.DataFrame()
    if gsc_df is None:
        gsc_df = pd.DataFrame()
        
    opportunities = {}
    
    # Rule A: High traffic + zero leads
    if not blog_df.empty and "Views" in blog_df.columns and "Key events" in blog_df.columns:
        p_val = thresholds.get("traffic_percentile", 0.75)
        cutoff = blog_df["Views"].quantile(p_val)
        opp_a = blog_df[(blog_df["Views"] >= cutoff) & (blog_df["Key events"] == 0)].copy()
        cols = [c for c in ["Page path and screen class", "Views", "Active users", "Key events"] if c in opp_a.columns]
        opportunities["high_traffic_zero_leads"] = opp_a[cols]
    else:
        opportunities["high_traffic_zero_leads"] = pd.DataFrame()
        
    # Rule B: High impressions + low CTR (GSC)
    if not gsc_df.empty and "Impressions" in gsc_df.columns and "CTR" in gsc_df.columns:
        imp_cutoff = gsc_df["Impressions"].quantile(0.50)
        ctr_cutoff = thresholds.get("low_ctr", 2.0)
        
        gsc_temp = gsc_df.copy()
        if gsc_temp["CTR"].max() <= 1.0:
            gsc_temp["CTR"] = gsc_temp["CTR"] * 100
            
        opp_b = gsc_temp[(gsc_temp["Impressions"] >= imp_cutoff) & (gsc_temp["CTR"] < ctr_cutoff)]
        opportunities["high_imp_low_ctr"] = opp_b
    else:
        opportunities["high_imp_low_ctr"] = pd.DataFrame()
        
    # Rule C: Position 10-20 terms (Low hanging fruit)
    if not gsc_df.empty and "Average position" in gsc_df.columns:
        pos_col = "Average position"
        opp_c = gsc_df[(gsc_df[pos_col] >= 10.0) & (gsc_df[pos_col] <= 20.0)].copy()
        opportunities["low_hanging_fruit"] = opp_c
    else:
        opportunities["low_hanging_fruit"] = pd.DataFrame()
        
    return opportunities