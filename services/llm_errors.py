"""User-facing LLM failure messages — never dump raw SDK JSON."""

from __future__ import annotations

import re

_QUOTA_MARKERS = (
    "429",
    "resource_exhausted",
    "insufficient_quota",
    "quota",
    "rate limit",
    "rate_limit",
    "limite ia",
    "limite atteinte",
)
_UNAVAILABLE_MARKERS = _QUOTA_MARKERS + (
    "aucun moteur",
    "absente des secrets",
    "absente dans les secrets",
    "réponse groq vide",
    "reponse groq vide",
    "connexion gemini impossible",
    "réponse vide",
    "reponse vide",
)


def is_llm_unavailable_error(exc: BaseException | str) -> bool:
    text = str(exc or "").lower()
    return any(marker in text for marker in _UNAVAILABLE_MARKERS)


def public_llm_error(exc: BaseException | str) -> str:
    """Short French message suitable for Streamlit error banners."""
    raw = str(exc or "").strip()
    lower = raw.lower()
    if any(marker in lower for marker in _QUOTA_MARKERS):
        return (
            "Limite IA atteinte (quota Gemini / Groq). "
            "Réessayez dans 1 à 2 minutes, ou ajoutez GROQ_API_KEY "
            "et d'autres clés Gemini dans les secrets Streamlit."
        )
    if "absente" in lower and "groq" in lower:
        return (
            "GROQ_API_KEY est absente des secrets. "
            "Ajoutez-la, ou une clé Gemini encore disponible."
        )
    if "vide" in lower:
        return (
            "Le moteur IA n'a pas renvoyé de texte. "
            "Réessayez, ou ajoutez une autre clé Groq / Gemini."
        )
    cleaned = re.sub(r"\{.*", "", raw, flags=re.S)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .:")
    if not cleaned:
        return "Génération IA indisponible. Réessayez dans quelques instants."
    return cleaned[:220]
