import streamlit as st
from src.data.loaders import detect_and_load_all
import pandas as pd

st.set_page_config(page_title="Data Quality", layout="wide")
st.title("🛡️ Data Quality & Ingestion Status")

datasets = detect_and_load_all()

if datasets:
    status_list = []
    for key, df in datasets.items():
        status_list.append({
            "Dataset Type": key,
            "Rows": len(df),
            "Columns": len(df.columns),
            "Missing Values": df.isnull().sum().sum(),
            "Duplicates": df.duplicated().sum(),
            "Status": "✅ Healthy" if not df.empty else "❌ Empty"
        })
        
    status_df = pd.DataFrame(status_list)
    st.dataframe(status_df, width="stretch")
else:
    st.error("No CSV files found in `data/input/`. Please check file placement.")