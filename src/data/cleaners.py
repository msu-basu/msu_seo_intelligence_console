import pandas as pd
from typing import Dict

COLUMN_ALIASES = {
    'users': 'Active users',
    'active users': 'Active users',
    'sessions': 'Sessions',
    'views': 'Views',
    'engagement rate': 'Engagement rate',
    'average engagement time': 'Average engagement time per active user',
    'key events': 'Key events',
    'conversions': 'Key events',
    'clicks': 'Clicks',
    'impressions': 'Impressions',
    'ctr': 'CTR',
    'position': 'Average position',
    'average position': 'Average position',
    'page': 'Page path and screen class',
    'page path': 'Page path and screen class',
    'page path and screen class': 'Page path and screen class'
}

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Maps varying column names to standardized canonical metric names."""
    if df.empty:
        return df
    
    new_cols = {}
    for col in df.columns:
        clean_col = col.strip().lower()
        if clean_col in COLUMN_ALIASES:
            new_cols[col] = COLUMN_ALIASES[clean_col]
        else:
            new_cols[col] = col
            
    return df.rename(columns=new_cols)

def normalize_urls(df: pd.DataFrame, url_col: str = 'Page path and screen class') -> pd.DataFrame:
    """Normalizes URL paths by stripping domain, parameters, and trailing slashes."""
    if df.empty or url_col not in df.columns:
        return df
        
    df[url_col] = df[url_col].astype(str)
    df[url_col] = df[url_col].apply(lambda x: x.split("msu.edu.in")[-1] if "msu.edu.in" in x else x)
    df[url_col] = df[url_col].str.split("?").str[0]
    df[url_col] = df[url_col].str.split("#").str[0]
    df[url_col] = df[url_col].apply(lambda x: x[:-1] if len(x) > 1 and x.endswith("/") else x)
    return df

def clean_blog_df(df: pd.DataFrame, url_col: str = 'Page path and screen class') -> pd.DataFrame:
    """Filters out admin, index, and non-article paths from blog analytics."""
    if df.empty or url_col not in df.columns:
        return df
        
    df = standardize_columns(df)
    df = normalize_urls(df, url_col)
    
    mask = (
        ~df[url_col].str.contains('/admin', case=False, na=False) &
        ~df[url_col].isin(['/blog', '/blog/', '/blog.html']) &
        ~df[url_col].str.startswith('#')
    )
    return df[mask].copy()