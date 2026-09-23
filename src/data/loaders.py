import pandas as pd
from pathlib import Path
from typing import Dict, Union, Tuple
from src.utils.logging import get_logger

logger = get_logger("loaders")

def get_skip_rows(filepath: Path) -> int:
    """Calculates metadata rows starting with '#' in GA4 exports."""
    skip = 0
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.startswith('#'):
                    skip += 1
                else:
                    break
    except Exception as e:
        logger.error(f"Error inspecting {filepath}: {e}")
    return skip

def load_csv_file(filepath: Union[str, Path]) -> pd.DataFrame:
    """Robustly reads a CSV file handling comment lines and alternative encodings."""
    path = Path(filepath)
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return pd.DataFrame()
    
    skip = get_skip_rows(path)
    encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']
    
    for enc in encodings:
        try:
            df = pd.read_csv(path, skiprows=skip, encoding=enc)
            df.columns = df.columns.str.strip()
            return df
        except Exception:
            continue
            
    logger.error(f"Failed to load CSV: {path}")
    return pd.DataFrame()

def detect_and_load_all(data_dir: Path = Path("data/input")) -> Dict[str, pd.DataFrame]:
    """Scans input directory and identifies files by column signature."""
    datasets = {}
    if not data_dir.exists():
        return datasets
        
    for file in data_dir.glob("*.csv"):
        df = load_csv_file(file)
        if df.empty:
            continue
            
        cols = [c.lower() for c in df.columns]
        filename = file.name.lower()
        
        if "device category" in cols:
            datasets["device"] = df
        elif "session source / medium" in cols or "00_overall" in filename:
            datasets["overall"] = df
        elif "event name" in cols or "05_events" in filename:
            datasets["events"] = df
        elif any("page" in c for c in cols):
            if "01_blog" in filename or "blog" in filename:
                datasets["blog"] = df
            elif "02_course" in filename or "course" in filename:
                datasets["course"] = df
            else:
                datasets["pages_generic"] = df
        elif "query" in cols or "clicks" in cols:
            datasets["gsc_queries"] = df
            
    return datasets