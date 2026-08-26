"""LLM usage helpers."""

from __future__ import annotations

from services.llm_usage import (
    bind_usage_user_id,
    current_usage_user_id,
    record_chat_usage,
    record_llm_usage,
    usage_from_gemini_payload,
    usage_from_openai_payload,
)


def test_usage_from_openai_dict():
    prompt, completion, total = usage_from_openai_payload(
        {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    )
    assert (prompt, completion, total) == (10, 5, 15)


def test_usage_from_gemini_payload():
    prompt, completion, total = usage_from_gemini_payload(
        {"usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 2, "totalTokenCount": 10}}
    )
    assert (prompt, completion, total) == (8, 2, 10)


def test_record_llm_usage_persists(sqlite_db):
    bind_usage_user_id(None)
    record_llm_usage(provider="groq", model="demo", total_tokens=42, user_id=None)
    from database import adapt_sql, connect

    with connect() as conn:
        row = conn.execute(adapt_sql("SELECT total_tokens, provider FROM llm_usage")).fetchone()
    assert int(row["total_tokens"]) == 42
    assert row["provider"] == "groq"


def test_record_chat_usage_estimates_when_missing(sqlite_db):
    record_chat_usage(
        provider="openai",
        model="gpt",
        usage=None,
        prompt_text="hello world " * 20,
        completion_text="ok",
    )
    from database import adapt_sql, connect

    with connect() as conn:
        row = conn.execute(adapt_sql("SELECT total_tokens FROM llm_usage")).fetchone()
    assert int(row["total_tokens"]) > 0


def test_bind_usage_user_id_context():
    bind_usage_user_id(99)
    assert current_usage_user_id() == 99
