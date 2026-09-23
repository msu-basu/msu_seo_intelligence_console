import plotly.express as px
import pandas as pd

def plot_bar_chart(df: pd.DataFrame, x: str, y: str, title: str, orientation: str = 'v'):
    """Renders a standard Plotly express bar chart using 'plotly_white' theme."""
    if df.empty or x not in df.columns or y not in df.columns:
        return None
        
    fig = px.bar(
        df, x=x, y=y, title=title, 
        orientation=orientation, 
        template="plotly_white",
        color_discrete_sequence=["#1f77b4"]
    )
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig

def plot_pie_chart(df: pd.DataFrame, values: str, names: str, title: str):
    """Renders a standard Plotly express pie chart."""
    if df.empty or values not in df.columns or names not in df.columns:
        return None
        
    fig = px.pie(df, values=values, names=names, title=title, template="plotly_white")
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig