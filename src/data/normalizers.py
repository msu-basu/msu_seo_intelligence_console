import pandas as pd
import yaml
from pathlib import Path

def categorize_course_url(path: str) -> str:
    """Categorizes course URL into academic hierarchy (PhD > Diploma > Postgraduate > Undergraduate > Other)."""
    p = str(path).lower()
    if 'phd' in p or 'doctoral' in p or 'doctor-of' in p:
        return 'PhD'
    elif 'diploma' in p:
        return 'Diploma'
    elif any(k in p for k in ['mba', 'master', 'm-sc', 'm-tech', 'm-voc', 'postgraduate']):
        return 'Postgraduate'
    elif any(k in p for k in ['btech', 'b-tech', 'bachelor', 'b-sc', 'bba', 'bca', 'b-voc', 'undergraduate']):
        return 'Undergraduate'
    return 'Other'

def apply_course_metadata(df: pd.DataFrame, url_col: str = 'Page path and screen class') -> pd.DataFrame:
    """Assigns program levels and loads manual mapping overrides."""
    if df.empty or url_col not in df.columns:
        return df
        
    df['Course Level'] = df[url_col].apply(categorize_course_url)
    
    mapping_file = Path("data/mappings/course_mapping.yaml")
    if mapping_file.exists():
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                mappings = yaml.safe_load(f)
                if mappings:
                    for url, meta in mappings.items():
                        if "level" in meta:
                            df.loc[df[url_col] == url, 'Course Level'] = meta["level"]
                        if "course_name" in meta:
                            df.loc[df[url_col] == url, 'Course Name'] = meta["course_name"]
        except Exception:
            pass
            
    if 'Course Name' not in df.columns:
        df['Course Name'] = df[url_col].str.replace('/course/', '').str.replace('-', ' ').str.title()
        
    return df