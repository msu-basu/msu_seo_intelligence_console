import pandas as pd
from src.data.cleaners import clean_blog_df

def get_blog_analytics(blog_df: pd.DataFrame) -> pd.DataFrame:
    """Prepares clean blog analytics dataset sorted by Views."""
    if blog_df.empty:
        return pd.DataFrame()
        
    cleaned = clean_blog_df(blog_df)
    
    if "Page path and screen class" in cleaned.columns:
        cleaned["Blog Title"] = cleaned["Page path and screen class"].str.replace("/blog/", "").str.replace("-", " ").str.title()
        
    numeric_cols = ["Views", "Active users", "Key events", "Average engagement time per active user"]
    for col in numeric_cols:
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce").fillna(0)
            
    return cleaned.sort_values(by="Views", ascending=False)