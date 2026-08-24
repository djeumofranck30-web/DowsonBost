"""Matching normalization tests."""

from __future__ import annotations

from services.matching import compute_ats_score, fallback_match_result, normalize_match_result


def test_compute_ats_score_weighted():
    score = compute_ats_score(
        {
            "score_competences": 80,
            "score_experiences": 60,
            "score_titre": 70,
            "score_localisation": 90,
        }
    )
    assert score == 74


def test_normalize_match_result_minimum_fields():
    job = {"title": "Python Developer"}
    result = normalize_match_result({"score_correspondance": 65}, job)
    assert result["score_correspondance"] == 65
    assert result["titre_cv_recommande"] == "Python Developer"
    assert len(result["conseils"]) >= 3


def test_fallback_match_result_flags_fallback():
    result = fallback_match_result({"title": "Data Engineer"})
    assert result["_fallback"] is True
    assert result["score_correspondance"] == 50
