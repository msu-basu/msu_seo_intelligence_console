import pandas as pd
from src.data.cleaners import standardize_columns, normalize_urls
from src.data.normalizers import apply_course_metadata

def get_course_analytics(course_df: pd.DataFrame) -> pd.DataFrame:
    """Prepares clean course dataset with level categorizations."""
    if course_df.empty:
        return pd.DataFrame()
        
    df = standardize_columns(course_df)
    df = normalize_urls(df)
    df = apply_course_metadata(df)
    
    numeric_cols = ["Views", "Active users", "Key events", "Sessions"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            
    return df.sort_values(by="Views", ascending=False)