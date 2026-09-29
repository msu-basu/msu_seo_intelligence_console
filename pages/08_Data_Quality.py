import streamlit as st
from src.data.loaders import detect_and_load_all
import pandas as pd

st.title("🛡️ Data Quality & Ingestion Status")

datasets = detect_and_load_all()

if datasets:
    status_list = []
    for key, df in datasets.items():
        date_col = next((c for c in df.columns if str(c).strip().lower() in ['date', 'report_date']), None)
        start_d = "N/A"
        end_d = "N/A"
        if date_col and not df.empty:
            s_series = pd.to_datetime(df[date_col], errors="coerce").dropna()
            if not s_series.empty:
                start_d = s_series.min().strftime("%Y-%m-%d")
                end_d = s_series.max().strftime("%Y-%m-%d")

        status_list.append({
            "Dataset Type": key,
            "Start Date": start_d,
            "End Date": end_d,
            "Rows": len(df),
            "Columns": len(df.columns),
            "Missing Values": df.isnull().sum().sum(),
            "Duplicates": df.duplicated().sum(),
            "Status": "✅ Healthy" if not df.empty else "❌ Empty"
        })
        
    status_df = pd.DataFrame(status_list)
    st.dataframe(status_df, width="stretch")
else:
    st.error("No CSV files found in `data/processed/`. Please check file placement.")
