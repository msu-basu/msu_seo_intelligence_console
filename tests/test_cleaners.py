import pandas as pd
from src.data.cleaners import clean_blog_df

def test_clean_blog_df():
    df = pd.DataFrame({
        "Page path and screen class": [
            "/blog/valid-article",
            "/admin/dashboard",
            "/blog/",
            "/blog"
        ],
        "Views": [100, 5, 50, 60]
    })
    
    cleaned = clean_blog_df(df)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["Page path and screen class"] == "/blog/valid-article"