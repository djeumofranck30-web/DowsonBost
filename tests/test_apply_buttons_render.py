"""Streamlit render of the two analysis apply buttons."""

from __future__ import annotations

from unittest.mock import patch

from streamlit.testing.v1 import AppTest


SCRIPT = """
from app import render_simple_job_row
from i18n import set_locale

set_locale("fr")
render_simple_job_row(
    {
        "title": "Développeur Python",
        "company": "Acme",
        "location": "Paris",
        "url": "https://www.acme.fr/jobs/1",
        "description": "Envoyez votre CV à recrutement@acme.fr",
    },
    {"score_correspondance": 88},
    1,
    result_id=11,
    user_id=1,
    cv_text="CV Jane",
    user_profile={"email": "jane@example.com", "full_name": "Jane Doe"},
)
"""


def test_analysis_row_renders_auto_and_manual_buttons() -> None:
    at = AppTest.from_string(SCRIPT)
    at.run()
    assert not at.exception
    labels = [button.label for button in at.button]
    assert "Analyser l'offre" in labels
    assert "Postuler automatiquement" in labels
    assert "Trouver l'e-mail recruteur (Hunter)" not in labels
    assert "J'ai postulé" not in labels
    auto = next(button for button in at.button if button.label == "Postuler automatiquement")
    assert "Hunter" in (auto.help or "")
    assert "e-mail" in (auto.help or "")
    manual = at.get("link_button")[0]
    assert manual.proto.label == "Postuler manuellement"
    assert manual.proto.url == "https://www.acme.fr/jobs/1"
    assert "vous-même" in manual.proto.help


def test_analysis_auto_button_records_email_send() -> None:
    at = AppTest.from_string(SCRIPT)
    at.run()
    sent = {
        "success": True,
        "method": "email",
        "message": (
            "Candidature envoyée automatiquement à recrutement@acme.fr. "
            "Un e-mail de confirmation vous a été envoyé à jane@example.com."
        ),
        "cover_letter": "Lettre",
        "adapted_cv": "CV adapté",
        "apply_email": "recrutement@acme.fr",
        "job_url": "https://www.acme.fr/jobs/1",
        "profile_text": "Jane",
        "user_notified": True,
    }
    with (
        patch("app.submit_application_automatically", return_value=sent) as submit,
        patch("app.save_generated_documents") as save_docs,
        patch("app.record_application") as record,
    ):
        auto = next(button for button in at.button if button.label == "Postuler automatiquement")
        auto.click().run()
    assert not at.exception
    submit.assert_called_once()
    save_docs.assert_called_once()
    record.assert_called_once()
    assert record.call_args.args[2] == "auto_email"
    assert "Candidature envoyée automatiquement" in at.success[0].value
