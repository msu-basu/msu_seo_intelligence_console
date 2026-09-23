import streamlit as st
import pandas as pd

def render_table_with_download(df: pd.DataFrame, filename: str = "export.csv", key: str = "df_table"):
    """Displays interactive dataframe with a CSV export button."""
    if df.empty:
        st.info("No data available to display.")
        return
        
    st.dataframe(df, width="stretch")
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv,
        file_name=filename,
        mime='text/csv',
        key=key
    )