"""Multiple Gemini/Groq keys for parallel ATS matching."""

from __future__ import annotations

import json
import types

from config import collect_raw_provider_api_keys, export_streamlit_secrets_to_environ
from constants import PARALLEL_MATCH_KEYS_PER_PROVIDER, PARALLEL_MATCH_MAX_WORKERS


def _aq_key(suffix: str) -> str:
    return f"AQ.Ab8testkey{suffix}xxxxxx"


def _gsk(suffix: str) -> str:
    return ("gsk_" + f"{suffix}x" * 30)[:56]


def _sk(suffix: str) -> str:
    return f"sk-testopenai{suffix}xxxxxxxxxxxx"


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


def test_rejects_gemini_example_placeholders() -> None:
    from app import _is_valid_provider_key

    assert not _is_valid_provider_key("gemini", "AQ.premiere_cle_...")
    assert not _is_valid_provider_key("gemini", "AQ.deuxieme_cle_...")
    assert not _is_valid_provider_key("gemini", "votre_cle_gemini")
    assert _is_valid_provider_key("gemini", _aq_key("1"))


def test_slots_use_all_gemini_groq_and_openai_together(monkeypatch) -> None:
    from app import collect_parallel_llm_slots

    monkeypatch.setenv("GEMINI_API_KEY", _aq_key("1"))
    monkeypatch.setenv("GEMINI_API_KEYS", json.dumps([_aq_key(str(i)) for i in range(2, 6)]))
    monkeypatch.setenv("GROQ_API_KEY", _gsk("1"))
    monkeypatch.setenv("GROQ_API_KEY_2", _gsk("2"))
    monkeypatch.setenv("OPENAI_API_KEY", _sk("1"))
    monkeypatch.delenv("GROQ_API_KEYS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
    for index in range(2, 9):
        monkeypatch.delenv(f"GEMINI_API_KEY_{index}", raising=False)
        if index != 2:
            monkeypatch.delenv(f"GROQ_API_KEY_{index}", raising=False)
        monkeypatch.delenv(f"OPENAI_API_KEY_{index}", raising=False)

    slots = collect_parallel_llm_slots()
    providers = [provider for provider, _key in slots]
    assert providers[:5] == ["gemini"] * 5
    assert providers.count("gemini") == 5
    assert providers.count("groq") == 2
    assert providers.count("openai") == 1
    assert len(slots) == 8


def test_call_llm_races_configured_providers(monkeypatch) -> None:
    import app as app_mod

    monkeypatch.setenv("GEMINI_API_KEY", _aq_key("1"))
    monkeypatch.setenv("GROQ_API_KEY", _gsk("1"))
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
    monkeypatch.delenv("GROQ_API_KEYS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
    for index in range(2, 9):
        monkeypatch.delenv(f"GEMINI_API_KEY_{index}", raising=False)
        monkeypatch.delenv(f"GROQ_API_KEY_{index}", raising=False)
        monkeypatch.delenv(f"OPENAI_API_KEY_{index}", raising=False)

    seen: list[str] = []

    def fake_direct(provider, *_args, **_kwargs):
        seen.append(provider)
        return f"ok-{provider}"

    monkeypatch.setattr(app_mod, "call_llm_direct", fake_direct)
    result = app_mod.call_llm("sys", "user")
    assert set(seen) == {"gemini", "groq"}
    assert result.startswith("ok-")


def test_gemini_reuses_cached_working_model(monkeypatch) -> None:
    import app as app_mod

    app_mod._GEMINI_WORKING_MODEL.clear()
    sdk_models: list[str] = []

    def fake_sdk(_parts, _system, model, api_key=None):
        sdk_models.append(model)
        return "ok", None

    fetch = types.SimpleNamespace(calls=0)

    def fake_fetch(_key=None):
        fetch.calls += 1
        return [], False

    monkeypatch.setattr(app_mod, "_gemini_via_sdk", fake_sdk)
    monkeypatch.setattr(app_mod, "_gemini_via_rest", lambda *_a, **_k: (None, "skip"))
    monkeypatch.setattr(app_mod, "_fetch_gemini_models_from_api", fake_fetch)
    app_mod._gemini_generate_content([{"text": "hi"}], api_key="AIza" + "x" * 32)
    app_mod._gemini_generate_content([{"text": "hi"}], api_key="AIza" + "x" * 32)
    assert fetch.calls == 0
    assert len(sdk_models) == 2
    assert sdk_models[0] == sdk_models[1]


def test_locale_keys_for_parallel_matching_exist() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for locale in ("fr", "en"):
        data = json.loads((root / f"locales/{locale}.json").read_text(encoding="utf-8"))
        assert "analysis.progress.match_keys" in data
        assert "analysis.parallel_keys" in data
        assert "analysis.parallel_keys_hint" in data
