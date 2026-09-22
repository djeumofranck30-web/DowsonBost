"""User-facing LLM error messages must stay short and JSON-free."""

from services.llm_errors import is_llm_unavailable_error, public_llm_error


def test_public_llm_error_strips_gemini_quota_json():
    raw = (
        "Impossible de générer les documents : Aucun moteur IA disponible "
        "groq : Réponse Groq vide. gemini : Connexion Gemini impossible "
        "(clé AQ.). gemini-3-flash-preview/SDK: 429 RESOURCE_EXHAUSTED "
        "{'error': {'code': 429, 'message': 'You exceeded your current quota'}}"
    )
    message = public_llm_error(raw)
    assert "Limite IA" in message
    assert "{" not in message
    assert "RESOURCE_EXHAUSTED" not in message


def test_public_llm_error_missing_groq_key():
    message = public_llm_error("groq : GROQ_API_KEY absente des secrets.")
    assert "GROQ_API_KEY" in message
    assert "absente" in message


def test_is_llm_unavailable_detects_quota_and_empty():
    assert is_llm_unavailable_error("429 RESOURCE_EXHAUSTED")
    assert is_llm_unavailable_error("Réponse Groq vide.")
    assert is_llm_unavailable_error("Aucun moteur IA disponible")
    assert not is_llm_unavailable_error("JSON invalide dans la réponse")
