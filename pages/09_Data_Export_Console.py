import io
import streamlit as st
import pandas as pd
from src.data.loaders import detect_and_load_all

st.set_page_config(page_title="Data Export Console", layout="wide")
st.title("📥 Data Export & Download Console")
st.caption("Inspect, filter, and export cleaned GA4 analytics and SEO datasets in CSV or Excel format.")

datasets = detect_and_load_all()

if not datasets:
    st.warning("⚠️ No datasets detected in `data/input/`. Upload your CSV files to enable downloads.")
else:
    # Friendly labels for datasets
    dataset_names = {
        "baseline": "00 - Overall Baseline GA4 Data",
        "blog": "01 - Blog Intelligence Dataset",
        "course": "02 - Academic Course Dataset",
        "device": "04 - Device Analysis Dataset",
        "events": "05 - GA4 Custom Events Dataset",
        "gsc_queries": "Google Search Console Queries"
    }

    available_keys = [k for k in dataset_names.keys() if k in datasets and not datasets[k].empty]
    if not available_keys:
        available_keys = list(datasets.keys())

    # Dataset Dropdown Selector
    selected_key = st.selectbox(
        "Select Dataset to Preview & Export:",
        options=available_keys,
        format_func=lambda k: dataset_names.get(k, k.replace("_", " ").title())
    )

    df = datasets[selected_key].copy()

    st.markdown("---")

    # Dataset Metrics Header
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Rows", f"{len(df):,}")
    col2.metric("Total Columns", f"{len(df.columns)}")
    
    views_col = next((c for c in ["Views", "Active users", "Clicks"] if c in df.columns), None)
    if views_col:
        total_val = pd.to_numeric(df[views_col], errors='coerce').fillna(0).sum()
        col3.metric(f"Total {views_col}", f"{int(total_val):,}")
    else:
        col3.metric("Dataset Status", "Ready for Export")

    st.markdown("---")

    # Dynamic Search & Column Customization
    st.subheader("1. Preview & Filter Data")
    
    search_query = st.text_input("🔍 Search within dataset (filters across all text fields):", "")
    
    if search_query:
        mask = df.astype(str).apply(lambda row: row.str.contains(search_query, case=False, na=False)).any(axis=1)
        df_display = df[mask]
        st.info(f"Filtered down to {len(df_display)} matching rows.")
    else:
        df_display = df

    selected_columns = st.multiselect(
        "Select specific columns to download (leave default for all):",
        options=list(df.columns),
        default=list(df.columns)
    )

    df_export = df_display[selected_columns] if selected_columns else df_display

    # Interactive Table
    st.dataframe(df_export, width="stretch", height=350)

    st.markdown("---")

    # Download Section
    st.subheader("2. Manual File Downloads")
    d_col1, d_col2 = st.columns(2)

    # CSV Download Button
    csv_bytes = df_export.to_csv(index=False).encode("utf-8")
    d_col1.download_button(
        label=f"📄 Download CSV ({len(df_export):,} Rows)",
        data=csv_bytes,
        file_name=f"export_{selected_key}.csv",
        mime="text/csv",
        type="primary"
    )

    # Excel Download Button
    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="GA4_Export")
        excel_data = buffer.getvalue()

        d_col2.download_button(
            label=f"📊 Download Excel Workbook (.xlsx)",
            data=excel_data,
            file_name=f"export_{selected_key}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception:
        d_col2.info("💡 Install `openpyxl` (`pip install openpyxl`) to enable direct Excel exports.")