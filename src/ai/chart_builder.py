"""
chart_builder.py
Intelligent chart generator for SQL query results in the AI Chatbot.
Produces interactive, beautifully styled Plotly charts matching console dark UI.
"""
from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

DARK_LAYOUT = dict(
    paper_bgcolor="rgba(15, 23, 42, 0.8)",
    plot_bgcolor="rgba(15, 23, 42, 0.6)",
    font=dict(color="#f1f5f9", family="Inter, sans-serif"),
    margin=dict(l=30, r=30, t=40, b=30),
    xaxis=dict(gridcolor="#334155", zerolinecolor="#475569"),
    yaxis=dict(gridcolor="#334155", zerolinecolor="#475569"),
    legend=dict(bgcolor="rgba(15, 23, 42, 0.7)", font=dict(color="#94a3b8")),
)

def build_chart_for_dataframe(df: pd.DataFrame, title: Optional[str] = None) -> Optional[go.Figure]:
    """
    Inspects DataFrame columns and row count, automatically choosing the optimal chart:
    - Time-series line chart if a date column exists.
    - Donut chart for small categorical breakdowns (e.g. device, channel <= 6 rows).
    - Horizontal bar chart for ranked categories (pages, queries, countries <= 20 rows).
    Returns None if DataFrame is empty or not suitable for graphical visualization.
    """
    if df.empty or len(df) == 0:
        return None

    cols = list(df.columns)
    if len(cols) < 2:
        return None

    # Detect date column
    date_cols = [c for c in cols if "date" in c.lower() or pd.api.types.is_datetime64_any_dtype(df[c])]
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c]) and c not in date_cols]
    text_cols = [c for c in cols if c not in date_cols and c not in numeric_cols]

    # 1. Time Series Chart
    if date_cols and numeric_cols:
        d_col = date_cols[0]
        y_col = numeric_cols[0]
        color_col = text_cols[0] if text_cols else None

        df_sorted = df.copy()
        df_sorted[d_col] = pd.to_datetime(df_sorted[d_col], errors="coerce")
        df_sorted = df_sorted.dropna(subset=[d_col]).sort_values(by=d_col)

        if color_col:
            fig = px.line(
                df_sorted,
                x=d_col,
                y=y_col,
                color=color_col,
                title=title or f"{y_col} Over Time by {color_col}",
                template="plotly_dark",
            )
        else:
            fig = px.area(
                df_sorted,
                x=d_col,
                y=y_col,
                title=title or f"{y_col} Over Time",
                template="plotly_dark",
            )
            fig.update_traces(line_color="#38bdf8", fillcolor="rgba(56, 189, 248, 0.2)")

        fig.update_layout(**DARK_LAYOUT)
        return fig

    # 2. Donut Chart for small categories (e.g. devices, channels)
    if text_cols and numeric_cols and 2 <= len(df) <= 6:
        cat_col = text_cols[0]
        val_col = numeric_cols[0]
        fig = px.pie(
            df,
            names=cat_col,
            values=val_col,
            hole=0.45,
            title=title or f"{val_col} Distribution by {cat_col}",
            template="plotly_dark",
            color_discrete_sequence=["#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#f43f5e", "#a78bfa"]
        )
        fig.update_layout(**DARK_LAYOUT)
        return fig

    # 3. Horizontal Bar Chart for Rankings (e.g. Top Pages, Top Queries, Top Countries)
    if text_cols and numeric_cols and 2 <= len(df) <= 25:
        cat_col = text_cols[0]
        val_col = numeric_cols[0]
        
        # Sort values ascending for horizontal bar (highest at top)
        df_sorted = df.sort_values(by=val_col, ascending=True).tail(15).copy()
        # Truncate long URLs or query names for clean labels
        df_sorted["_display_label"] = df_sorted[cat_col].astype(str).apply(
            lambda x: (x[:45] + "...") if len(x) > 48 else x
        )

        fig = px.bar(
            df_sorted,
            x=val_col,
            y="_display_label",
            orientation="h",
            title=title or f"Top {len(df_sorted)} by {val_col}",
            template="plotly_dark",
            text=val_col,
        )
        fig.update_traces(
            marker_color="#38bdf8",
            texttemplate="%{text:,.0f}",
            textposition="outside",
        )
        fig.update_layout(**DARK_LAYOUT)
        fig.update_yaxes(title="")
        return fig

    return None

