"""Multiple Gemini/Groq keys for parallel ATS matching."""

from __future__ import annotations

import json
import types

from config import collect_raw_provider_api_keys, export_streamlit_secrets_to_environ
from constants import PARALLEL_MATCH_KEYS_PER_PROVIDER, PARALLEL_MATCH_MAX_WORKERS


def _aq_key(suffix: str) -> str:
    return f"AQ.Ab8testkey{suffix}xxxxxx"


def test_constants_allow_five_gemini_keys() -> None:
    assert PARALLEL_MATCH_KEYS_PER_PROVIDER >= 5
    assert PARALLEL_MATCH_MAX_WORKERS >= 5


def test_collects_five_numbered_gemini_keys(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", _aq_key("1"))
    for index in range(2, 9):
        monkeypatch.delenv(f"GEMINI_API_KEY_{index}", raising=False)
    for index in range(2, 6):
        monkeypatch.setenv(f"GEMINI_API_KEY_{index}", _aq_key(str(index)))
    keys = collect_raw_provider_api_keys("gemini")
    assert keys[:5] == [_aq_key(str(i)) for i in range(1, 6)]
    assert len(keys) == 5


def test_collects_five_gemini_keys_from_json_list(monkeypatch) -> None:
    extras = [_aq_key(str(i)) for i in range(2, 6)]
    monkeypatch.setenv("GEMINI_API_KEY", _aq_key("1"))
    monkeypatch.setenv("GEMINI_API_KEYS", json.dumps(extras))
    for index in range(2, 9):
        monkeypatch.delenv(f"GEMINI_API_KEY_{index}", raising=False)
    keys = collect_raw_provider_api_keys("gemini")
    assert keys == [_aq_key("1"), *extras]


def test_export_keeps_all_gemini_list_keys(monkeypatch) -> None:
    import config

    config._secrets_exported = False
    extras = [_aq_key(str(i)) for i in range(2, 6)]
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
    for index in range(2, 9):
        monkeypatch.delenv(f"GEMINI_API_KEY_{index}", raising=False)
    fake_st = types.SimpleNamespace(
        secrets={"GEMINI_API_KEYS": extras}
    )
    monkeypatch.setitem(__import__("sys").modules, "streamlit", fake_st)
    export_streamlit_secrets_to_environ()
    keys = collect_raw_provider_api_keys("gemini")
    assert extras == [item for item in keys if item in extras]
    assert len(extras) == 4


def test_five_gemini_keys_fit_parallel_matching_cap(monkeypatch) -> None:
    keys = [_aq_key(str(i)) for i in range(1, 6)]
    monkeypatch.setenv("GEMINI_API_KEY", keys[0])
    monkeypatch.setenv("GEMINI_API_KEYS", json.dumps(keys[1:]))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEYS", raising=False)
    for index in range(2, 9):
        monkeypatch.delenv(f"GROQ_API_KEY_{index}", raising=False)
        monkeypatch.delenv(f"GEMINI_API_KEY_{index}", raising=False)
    collected = collect_raw_provider_api_keys("gemini")
    assert collected[:PARALLEL_MATCH_KEYS_PER_PROVIDER] == keys
    assert len(collected) == 5
