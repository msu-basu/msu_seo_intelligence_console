"""
agent.py
Central AI Analytical Agent for the MSU SEO Intelligence Console.
Coordinates Text-to-SQL query generation, PostgreSQL execution,
analytical response synthesis, interactive chart building, and fallback modes.
"""
from __future__ import annotations

import re
from typing import Dict, Any, List, Optional
import pandas as pd

from src.ai.client import AIClient
from src.ai.schema_context import get_database_schema_prompt
from src.ai.sql_executor import execute_safe_sql
from src.ai.chart_builder import build_chart_for_dataframe
from src.ai.local_engine import process_local_query
from src.utils.logging import get_logger

logger = get_logger("ai_agent")

TEXT_TO_SQL_SYSTEM_PROMPT = f"""
{get_database_schema_prompt()}

### YOUR TASK:
Translate the user's natural language question into an exact, valid, read-only PostgreSQL query.
CRITICAL INSTRUCTIONS:
1. Output ONLY the raw SQL query inside a single ```sql ... ``` code block.
2. Do not write any conversational text, explanations, or greeting before or after the code block.
3. Write clean, standard PostgreSQL. Use views under the 'analytics' schema for page and query summaries when appropriate.
4. Wrap column names with spaces or mixed casing in double quotes: e.g. "Page path and screen class", "Views", "Active users", "Top queries", "Date".
5. Always apply a LIMIT (e.g. LIMIT 10, LIMIT 20) unless aggregating to a small scalar.
6. Strictly read-only: never produce INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or multiple statements.
7. MULTI-TURN CONVERSATION & CONTEXT RESOLUTION:
   - When the user asks a follow-up question (using pronouns like 'these', 'those', 'them', 'it', or relative phrasing like 'which of these had conversions?', 'show bounce rate', 'what about mobile?', 'compare that with...'), resolve the reference using the prior queries, executed SQL, and table context in the conversation history.
   - If the user changes topics or asks an independent question, generate the standalone SQL query for the new topic.
"""

SYNTHESIS_SYSTEM_PROMPT = """
You are the Principal Strategy & Analytics Partner advising the Executive Board of Medhavi Skills University (MSU SEO Intelligence Console).
Your goal is to transform quantitative query data into a compelling, descriptive, and actionable narrative (The Pyramid Principle / BLUF).

INSTITUTIONAL DOMAIN CONTEXT & SYSTEMIC DRIVERS:
Medhavi Skills University (MSU) provides industry-sponsored, skill-integrated degree programs across Emerging Technologies (B.Tech in AI/ML), Allied Healthcare (Paramedical, Radiology, Operation Theatre Technology), and Hospitality. The digital conversion lifecycle depends on transitioning informational career searchers into qualified admission leads (form inquiries and counselor callbacks). The audience primarily comprises 12th-grade students, tier-2/3 aspirants, and working professionals seeking career switch credentials.

OUTPUT FORMAT & STRUCTURAL RULES:
- STRICT ZERO-NUMBERING: NEVER use numbered point prefixes like "1.", "2.", "Point 1", "Point 2", "1. BLUF", or "2. Data". Write point-to-point in clean narrative prose.
- The Executive Summary must be a cohesive, high-impact paragraph synthesizing the core finding, key volume/conversion numbers, and operational reality without bullet points or numbering.
- Structure your response using EXACTLY these markdown headers:

### 📌 Summary
[A single, high-impact narrative paragraph synthesizing the core finding, key volume/conversion numbers, and operational reality without any numbered list format]

### 🔍 Quantitative Narrative & Findings
- Key observation with specific data points, volumes, or percentages
- Comparison against historical cohorts, targets, or baseline
- Drop-off cliff, variance, or concentration pattern

### 💡 Strategic Root Cause
[A descriptive narrative paragraph examining the operational, student, market, or human decision drivers behind the numbers]

### 🎯 Leadership Action Playbook
- Actionable initiative with expected conversion or revenue impact
- Immediate operational intervention for frontline counselors or marketing
"""


def extract_sql_from_response(text: str) -> str:
    """Extracts SQL query from LLM output, handling markdown code fences."""
    text = text.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # If no code block, look for SELECT statement
    select_match = re.search(r"(SELECT\s+.*)", text, re.DOTALL | re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip()
    
    return text.strip()


def extract_follow_ups_from_text(text: str) -> List[str]:
    """Extracts follow up questions from generated text if present."""
    follow_ups = []
    if "Suggested Next Questions:" in text or "Suggested Questions:" in text:
        parts = re.split(r"💡\s*\*\*Suggested (?:Next )?Questions:\*\*", text, flags=re.IGNORECASE)
        if len(parts) > 1:
            raw_questions = parts[1].strip().splitlines()
            for line in raw_questions:
                clean_q = re.sub(r"^[\s*\-•\d.]+", "", line).strip()
                if clean_q and len(clean_q) > 8 and clean_q.endswith("?"):
                    follow_ups.append(clean_q)
    return follow_ups[:3]


def ask_ai_analyst(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main orchestration function for the AI Data Analyst.
    Returns:
    {
        "answer": str,
        "sql": str,
        "df": pd.DataFrame,
        "execution_time_ms": float,
        "chart": Optional[go.Figure],
        "follow_ups": List[str]
    }
    """
    if history is None:
        history = []

    client = AIClient(provider=provider, api_key=api_key, model=model)

    # 1. Fallback to Local Engine if provider is local or credentials are not configured
    if client.provider == "local" or not client.has_valid_credentials():
        logger.info("Using Local Zero-API-Key Engine for prompt: %s (history items: %d)", prompt, len(history))
        return process_local_query(prompt, history=history)

    try:
        # 2. Step 1: Generate SQL query from natural language with multi-turn context
        messages = []
        for msg in history[-6:]:  # Keep recent context (last 3 interactions)
            role = msg.get("role", "user")
            if role == "user":
                messages.append({"role": "user", "content": msg.get("content", "")})
            else:
                # Provide concise context of previous assistant query rather than massive essay
                sql_q = msg.get("sql", "").strip()
                if sql_q:
                    messages.append({"role": "assistant", "content": f"Executed PostgreSQL Query:\n```sql\n{sql_q}\n```"})
                else:
                    first_line = msg.get("content", "").split("\n")[0][:120]
                    messages.append({"role": "assistant", "content": first_line})
        messages.append({"role": "user", "content": prompt})

        llm_sql_response = client.generate_chat_response(
            messages=messages,
            system_prompt=TEXT_TO_SQL_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=600,
        )

        extracted_sql = extract_sql_from_response(llm_sql_response)
        logger.info("Generated SQL: %s", extracted_sql)

        # 3. Step 2: Execute SQL against PostgreSQL
        df, execution_time_ms, error = execute_safe_sql(extracted_sql)

        # If error occurs, attempt 1 automatic correction retry with LLM
        if error:
            logger.warning("Initial SQL failed with error: %s. Retrying with error correction.", error)
            correction_messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": f"```sql\n{extracted_sql}\n```"},
                {"role": "user", "content": f"The PostgreSQL database returned this error:\n{error}\nPlease correct the SQL query to resolve this error. Output ONLY the corrected query inside ```sql ... ```."}
            ]
            corrected_llm_response = client.generate_chat_response(
                messages=correction_messages,
                system_prompt=TEXT_TO_SQL_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=600,
            )
            extracted_sql = extract_sql_from_response(corrected_llm_response)
            df, execution_time_ms, error = execute_safe_sql(extracted_sql)

        # If still error, fall back gracefully to local engine with history
        if error or df.empty:
            if error:
                logger.warning("LLM SQL execution failed after correction: %s. Falling back to local engine.", error)
                local_result = process_local_query(prompt, history=history)
                local_result["answer"] = f"*(Note: LLM SQL query encountered a PostgreSQL error: `{error}`. Falling back to local analytical rules)*\n\n" + local_result["answer"]
                return local_result

        # 4. Step 3: Synthesize analytical answer with LLM using the returned data and prior context
        data_sample_str = df.head(25).to_markdown(index=False)
        total_rows = len(df)
        columns_str = ", ".join(df.columns)

        prior_context_parts = []
        for h in history[-4:]:
            r = "User" if h.get("role") == "user" else "Assistant"
            first_bit = h.get("content", "").split("\n")[0][:180]
            prior_context_parts.append(f"- {r}: {first_bit}")
        prior_context_str = "\n".join(prior_context_parts)
        prior_block = f"\n### CONVERSATION MEMORY & PRIOR TURNS:\n{prior_context_str}\n" if prior_context_str else ""

        synthesis_prompt = f"""
{prior_block}
User's Question: "{prompt}"

PostgreSQL Query Executed:
{extracted_sql}

Query Performance: {execution_time_ms:.1f}ms | Total Rows Retrieved: {total_rows}
Columns: {columns_str}

Data Sample (first {min(25, total_rows)} rows):
{data_sample_str}

Please provide your executive analytical interpretation and actionable SEO/content insights based strictly on this data.
If this question connects with or follows up on prior questions in the conversation, explicitly weave those insights together for a comprehensive briefing.
"""
        synthesis_messages = [
            {"role": "user", "content": synthesis_prompt}
        ]

        synthesized_answer = client.generate_chat_response(
            messages=synthesis_messages,
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=1500,
        )

        follow_ups = extract_follow_ups_from_text(synthesized_answer)
        if not follow_ups:
            follow_ups = [
                "What are the top 10 blog posts by views?",
                "What is our traffic breakdown across devices?",
                "Which queries have high impressions but low CTR?"
            ]

        # 5. Step 4: Build interactive chart
        chart = build_chart_for_dataframe(df)

        return {
            "answer": synthesized_answer,
            "sql": extracted_sql,
            "df": df,
            "execution_time_ms": execution_time_ms,
            "chart": chart,
            "follow_ups": follow_ups
        }

    except Exception as e:
        logger.error("Error in AI analyst orchestration: %s", e)
        # Graceful fallback to local engine on any network or API failure
        local_result = process_local_query(prompt, history=history)
        local_result["answer"] = f"*(Notice: AI API communication error: `{e}`. Responding using local analytical database engine)*\n\n" + local_result["answer"]
        return local_result

