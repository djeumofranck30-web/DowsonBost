"""Record LLM token consumption per user for the admin dashboard."""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from database import adapt_sql, connect, database_backend
from observability import get_logger

logger = get_logger(__name__)

_usage_user_id: ContextVar[int | None] = ContextVar("llm_usage_user_id", default=None)
_table_ready = False


def bind_usage_user_id(user_id: int | None) -> None:
    """Attach the current candidate to subsequent LLM usage rows (thread-safe)."""
    if user_id is None:
        _usage_user_id.set(None)
        return
    try:
        _usage_user_id.set(int(user_id))
    except (TypeError, ValueError):
        _usage_user_id.set(None)


def bind_current_user_from_streamlit() -> None:
    """Read Streamlit session user id when the context var is empty."""
    if _usage_user_id.get() is not None:
        return
    try:
        import streamlit as st

        user = st.session_state.get("user") or {}
        uid = user.get("id") or st.session_state.get("user_id")
        if uid is not None:
            _usage_user_id.set(int(uid))
    except Exception:  # noqa: BLE001 — usage tracking must never break LLM calls
        return


def current_usage_user_id() -> int | None:
    bound = _usage_user_id.get()
    if bound is not None:
        return bound
    bind_current_user_from_streamlit()
    return _usage_user_id.get()


def estimate_tokens(*texts: str) -> int:
    """Rough token count when the provider does not return usage (~4 chars / token)."""
    total_chars = sum(len(text or "") for text in texts)
    return max(1, total_chars // 4)


def ensure_llm_usage_table() -> None:
    """Create the llm_usage table if needed."""
    global _table_ready
    if _table_ready:
        return
    with connect() as conn:
        _create_llm_usage_table(conn)
    _table_ready = True


def _create_llm_usage_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS llm_usage_user_created_idx
            ON llm_usage (user_id, created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS llm_usage_created_idx
            ON llm_usage (created_at DESC)
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            created_at TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT '',
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS llm_usage_user_created_idx
        ON llm_usage (user_id, created_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS llm_usage_created_idx
        ON llm_usage (created_at DESC)
        """
    )


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def usage_from_openai_payload(usage: Any) -> tuple[int, int, int]:
    """Normalize OpenAI/Groq usage objects or dicts."""
    if usage is None:
        return 0, 0, 0
    if isinstance(usage, dict):
        prompt = _as_int(usage.get("prompt_tokens") or usage.get("promptTokenCount"))
        completion = _as_int(
            usage.get("completion_tokens")
            or usage.get("completionTokenCount")
            or usage.get("candidatesTokenCount")
        )
        total = _as_int(usage.get("total_tokens") or usage.get("totalTokenCount"))
    else:
        prompt = _as_int(getattr(usage, "prompt_tokens", 0) or getattr(usage, "prompt_token_count", 0))
        completion = _as_int(
            getattr(usage, "completion_tokens", 0)
            or getattr(usage, "candidates_token_count", 0)
            or getattr(usage, "completion_token_count", 0)
        )
        total = _as_int(getattr(usage, "total_tokens", 0) or getattr(usage, "total_token_count", 0))
    if total <= 0:
        total = prompt + completion
    return prompt, completion, total


def usage_from_gemini_payload(data: Any) -> tuple[int, int, int]:
    meta = None
    if isinstance(data, dict):
        meta = data.get("usageMetadata") or data.get("usage_metadata")
    else:
        meta = getattr(data, "usage_metadata", None)
    return usage_from_openai_payload(meta)


def record_llm_usage(
    *,
    provider: str,
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    user_id: int | None = None,
    prompt_text: str = "",
    completion_text: str = "",
) -> None:
    """Persist one LLM call. Never raises to the caller."""
    try:
        ensure_llm_usage_table()
        uid = user_id if user_id is not None else current_usage_user_id()
        prompt_n = _as_int(prompt_tokens)
        completion_n = _as_int(completion_tokens)
        total_n = _as_int(total_tokens)
        if total_n <= 0:
            total_n = prompt_n + completion_n
        if total_n <= 0:
            total_n = estimate_tokens(prompt_text, completion_text)
            prompt_n = estimate_tokens(prompt_text) if prompt_text else 0
            completion_n = max(0, total_n - prompt_n)
        provider_id = (provider or "unknown").strip().lower() or "unknown"
        model_id = (model or "").strip()
        with connect() as conn:
            conn.execute(
                adapt_sql(
                    """
                    INSERT INTO llm_usage (
                        user_id, created_at, provider, model,
                        prompt_tokens, completion_tokens, total_tokens
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    int(uid) if uid is not None else None,
                    datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    provider_id,
                    model_id,
                    prompt_n,
                    completion_n,
                    total_n,
                ),
            )
    except Exception:  # noqa: BLE001
        logger.debug("Could not record LLM usage", exc_info=True)


def record_chat_usage(
    *,
    provider: str,
    model: str = "",
    usage: Any = None,
    prompt_text: str = "",
    completion_text: str = "",
    user_id: int | None = None,
) -> None:
    prompt_n, completion_n, total_n = usage_from_openai_payload(usage)
    record_llm_usage(
        provider=provider,
        model=model,
        prompt_tokens=prompt_n,
        completion_tokens=completion_n,
        total_tokens=total_n,
        user_id=user_id,
        prompt_text=prompt_text,
        completion_text=completion_text,
    )
