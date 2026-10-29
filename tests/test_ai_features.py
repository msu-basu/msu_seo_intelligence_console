"""
test_ai_features.py
Comprehensive test suite for AI Compatibility, SQL safety guardrails,
LLM client configurations, chart generation, and local query execution.
"""
import pytest
import pandas as pd
from datetime import date

from src.ai.client import AIClient, PROVIDERS_CONFIG
from src.ai.sql_executor import sanitize_sql_query, execute_safe_sql
from src.ai.agent import extract_sql_from_response, extract_follow_ups_from_text
from src.ai.chart_builder import build_chart_for_dataframe
from src.ai.local_engine import _build_sql_for_intent, _synthesize_local_answer
from src.insights.ai_summary import generate_deterministic_summary, generate_ai_executive_summary


# =============================================================================
# 1. AI CLIENT & CONFIG TESTS
# =============================================================================

def test_providers_config():
    """Verify all supported providers are properly configured."""
    assert "gemini" in PROVIDERS_CONFIG
    assert "openai" in PROVIDERS_CONFIG
    assert "groq" in PROVIDERS_CONFIG
    assert "ollama" in PROVIDERS_CONFIG
    assert "local" in PROVIDERS_CONFIG

    assert PROVIDERS_CONFIG["gemini"]["default_model"] == "gemini-2.5-flash"
    assert "gpt-4o-mini" in PROVIDERS_CONFIG["openai"]["models"]


def test_ai_client_credential_detection():
    """Verify credential validation across providers."""
    # Local engine needs no credentials
    local_client = AIClient(provider="local")
    assert local_client.has_valid_credentials() is True

    # Ollama needs no external key
    ollama_client = AIClient(provider="ollama")
    assert ollama_client.has_valid_credentials() is True

    # Gemini without key
    gemini_client_nokey = AIClient(provider="gemini", api_key="")
    assert gemini_client_nokey.has_valid_credentials() is False

    # Gemini with key
    gemini_client_withkey = AIClient(provider="gemini", api_key="AIzaSyDummyKey123456789")
    assert gemini_client_withkey.has_valid_credentials() is True


def test_ai_client_missing_key_raises():
    """Verify generate_chat_response raises ValueError when key is missing."""
    client = AIClient(provider="openai", api_key="")
    with pytest.raises(ValueError, match="Missing API key"):
        client.generate_chat_response(messages=[{"role": "user", "content": "Hello"}])


# =============================================================================
# 2. SQL SAFETY & GUARDRAILS TESTS
# =============================================================================

def test_sanitize_sql_valid_queries():
    """Verify valid SELECT queries pass sanitization."""
    q1 = 'SELECT "Page path and screen class", "Views" FROM analytics.v_blog_page_summary LIMIT 10;'
    is_safe, clean, err = sanitize_sql_query(q1)
    assert is_safe is True
    assert err is None
    assert "SELECT" in clean

    # Code block wrapping should be stripped
    q2 = '```sql\nSELECT * FROM raw.ga4_device;\n```'
    is_safe, clean, err = sanitize_sql_query(q2)
    assert is_safe is True
    assert "LIMIT 100" in clean  # Automatic limit appended


def test_sanitize_sql_with_cte():
    """Verify WITH ... SELECT queries are allowed."""
    q = 'WITH ranked AS (SELECT * FROM raw.ga4_events) SELECT * FROM ranked LIMIT 5;'
    is_safe, clean, err = sanitize_sql_query(q)
    assert is_safe is True
    assert clean.startswith("WITH")


def test_sanitize_sql_blocks_dangerous_keywords():
    """Ensure all destructive and modification queries are blocked."""
    dangerous = [
        "DROP TABLE raw.ga4_blog_daily;",
        "DELETE FROM raw.ga4_course_daily WHERE views = 0;",
        "UPDATE raw.ga4_device SET active_users = 0;",
        "INSERT INTO raw.ga4_events VALUES (1, 'hack');",
        "ALTER TABLE raw.ga4_geo_global DROP COLUMN city;",
        "TRUNCATE TABLE raw.ga4_overall_baseline;",
        "CREATE TABLE test (id INT);",
        "GRANT ALL PRIVILEGES ON DATABASE web_analytics TO public;",
    ]
    for bad_sql in dangerous:
        is_safe, clean, err = sanitize_sql_query(bad_sql)
        assert is_safe is False, f"Should have blocked: {bad_sql}"
        assert err is not None


def test_sanitize_sql_blocks_chaining():
    """Ensure semicolon chaining is blocked to prevent SQL injection."""
    chained = "SELECT * FROM raw.ga4_device; DROP TABLE raw.ga4_device;"
    is_safe, clean, err = sanitize_sql_query(chained)
    assert is_safe is False
    assert "Multiple statements" in err


def test_execute_safe_sql_rejects_unsafe():
    """Verify execute_safe_sql returns error without executing dangerous query."""
    df, ms, err = execute_safe_sql("DROP TABLE test;")
    assert df.empty
    assert "Query Security Rejection" in err


# =============================================================================
# 3. SQL EXTRACTION & SYNTHESIS TESTS
# =============================================================================

def test_extract_sql_from_response():
    """Verify SQL extraction from various LLM response formats."""
    # Fenced with ```sql
    resp1 = "Here is the query:\n```sql\nSELECT * FROM analytics.v_blog_page_summary LIMIT 10;\n```\nHope this helps!"
    assert extract_sql_from_response(resp1) == "SELECT * FROM analytics.v_blog_page_summary LIMIT 10;"

    # Fenced without language tag
    resp2 = "```\nSELECT * FROM raw.ga4_device LIMIT 5;\n```"
    assert extract_sql_from_response(resp2) == "SELECT * FROM raw.ga4_device LIMIT 5;"

    # Plain text query
    resp3 = "SELECT \"Date\", \"Views\" FROM analytics.v_daily_traffic_trends LIMIT 20;"
    assert extract_sql_from_response(resp3) == "SELECT \"Date\", \"Views\" FROM analytics.v_daily_traffic_trends LIMIT 20;"


def test_extract_follow_ups():
    """Verify follow-up questions are parsed from synthesis response."""
    text = """
    Here are the top performing courses.
    
    💡 **Suggested Next Questions:**
    1. Which courses have the lowest bounce rate?
    2. What are the top search queries for paramedical programs?
    """
    follow_ups = extract_follow_ups_from_text(text)
    assert len(follow_ups) == 2
    assert "Which courses have the lowest bounce rate?" in follow_ups
    assert "What are the top search queries for paramedical programs?" in follow_ups


# =============================================================================
# 4. CHART BUILDER TESTS
# =============================================================================

def test_build_chart_time_series():
    """Verify time series DataFrame produces a Plotly Figure."""
    df = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=10),
        "Views": [100, 150, 120, 200, 180, 220, 210, 250, 300, 280],
        "Channel": ["Blog"] * 10
    })
    fig = build_chart_for_dataframe(df, title="Traffic Over Time")
    assert fig is not None
    assert fig.layout.title.text == "Traffic Over Time"


def test_build_chart_donut_devices():
    """Verify small categorical DataFrame produces a donut chart."""
    df = pd.DataFrame({
        "Device": ["mobile", "desktop", "tablet"],
        "Active Users": [249000, 84000, 1500]
    })
    fig = build_chart_for_dataframe(df)
    assert fig is not None


def test_build_chart_horizontal_bar_rankings():
    """Verify ranking DataFrame produces a horizontal bar chart."""
    df = pd.DataFrame({
        "Article": [f"/blog/post-{i}" for i in range(10)],
        "Views": [1000 - i * 50 for i in range(10)]
    })
    fig = build_chart_for_dataframe(df)
    assert fig is not None


def test_build_chart_empty_returns_none():
    """Verify empty DataFrame returns None."""
    assert build_chart_for_dataframe(pd.DataFrame()) is None


# =============================================================================
# 5. LOCAL ENGINE INTENT MAPPING TESTS
# =============================================================================

def test_local_engine_intent_mapping():
    """Verify natural language prompts map to appropriate SQL and titles."""
    sql, title, follow_ups = _build_sql_for_intent("Show me mobile vs desktop traffic")
    assert "raw.ga4_device" in sql
    assert "Device" in title
    assert len(follow_ups) > 0

    sql, title, follow_ups = _build_sql_for_intent("What are our daily traffic trends over time?")
    assert "analytics.v_daily_traffic_trends" in sql

    sql, title, follow_ups = _build_sql_for_intent("Which search queries have high impressions but low ctr?")
    assert "analytics.v_gsc_top_queries" in sql
    assert "CTR" in sql

    sql, title, follow_ups = _build_sql_for_intent("What are the top academic courses?")
    assert "analytics.v_course_page_summary" in sql


def test_synthesize_local_answer():
    """Verify answer synthesis handles DataFrames gracefully."""
    df = pd.DataFrame({
        "Device": ["mobile", "desktop"],
        "Active Users": [250000, 85000],
        "Leads (Key Events)": [2300, 3200]
    })
    answer = _synthesize_local_answer("devices", df, "Traffic by Device")
    assert "### 📌 Summary" in answer
    assert "### 🔍 Quantitative Narrative & Findings" in answer
    assert "250,000" in answer


# =============================================================================
# 6. EXECUTIVE SUMMARY INTEGRATION TESTS
# =============================================================================

def test_executive_summary_deterministic_and_ai_fallback():
    """Verify deterministic summary generation and AI fallback behavior."""
    summary_data = {
        "sessions": 125000,
        "views": 350000,
        "key_events": 5500,
        "gsc_clicks": 42000,
        "gsc_impressions": 1200000,
        "gsc_ctr": 3.5
    }
    det_text = generate_deterministic_summary(summary_data)
    assert "125,000" in det_text
    assert "5,500" in det_text
    assert "42,000" in det_text

    # AI summary with no key should seamlessly return deterministic summary
    ai_text = generate_ai_executive_summary(summary_data, provider="local")
    assert "125,000" in ai_text


# =============================================================================
# 7. MULTI-TURN CONVERSATIONAL MEMORY TESTS
# =============================================================================

def test_local_engine_multi_turn_course_follow_up():
    """Verify follow-up questions inherit context from previous course query."""
    history = [
        {"role": "user", "content": "What are the top academic courses by views?"},
        {
            "role": "assistant",
            "content": "### 📌 Summary\nTop courses include B.Tech AI and Paramedical.",
            "sql": 'SELECT "Page path and screen class" AS "Course Page", "Views" FROM analytics.v_course_page_summary LIMIT 10;'
        }
    ]
    # Follow-up with ambiguous pronoun "these"
    sql, title, follow_ups = _build_sql_for_intent("Which of these had conversions?", history=history)
    assert "v_course_page_summary" in sql
    assert "Conversions" in sql
    assert "Course" in title


def test_local_engine_multi_turn_blog_follow_up():
    """Verify follow-up questions inherit context from previous blog query."""
    history = [
        {"role": "user", "content": "Show me top 10 blog posts"},
        {
            "role": "assistant",
            "content": "### 📌 Summary\nHere are the top blog articles.",
            "sql": 'SELECT "Page path and screen class" AS "Article Path", "Views" FROM analytics.v_blog_page_summary LIMIT 10;'
        }
    ]
    sql, title, follow_ups = _build_sql_for_intent("Which ones had highest conversions?", history=history)
    assert "v_blog_page_summary" in sql
    assert "Conversions" in sql
    assert "Blog" in title


def test_ask_ai_analyst_multi_turn_end_to_end():
    """Verify ask_ai_analyst processes multi-turn history without exceptions."""
    from src.ai.agent import ask_ai_analyst
    history = [
        {"role": "user", "content": "Top courses"},
        {
            "role": "assistant",
            "content": "### 📌 Summary\nCourses include AI/ML.",
            "sql": 'SELECT * FROM analytics.v_course_page_summary LIMIT 5;'
        }
    ]
    res = ask_ai_analyst("Which of these had conversions?", history=history, provider="local")
    assert "answer" in res
    assert "### 📌 Summary" in res["answer"]
    assert res.get("sql") is not None


