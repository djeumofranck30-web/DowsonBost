"""Spec alignment: salary/remote filters, DOCX, GDPR, freelance, no duplicate apply."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from auth import authenticate_user, register_user, update_user_profile
from document_generation import (
    generate_followup_message,
    generate_freelance_proposal,
    generate_freelance_quote,
)
from job_filters import (
    apply_strict_job_filters,
    infer_job_salary_min,
    infer_job_work_mode,
    job_matches_salary,
    job_matches_work_mode,
    parse_annual_salary_eur,
)
from job_providers import (
    JOB_PROVIDER_CHOICES,
    JOB_PROVIDER_FRANCE_TRAVAIL,
    JOB_PROVIDER_FREELANCE,
    JOB_PROVIDER_SIDEBAR_ORDER,
    configured_providers,
    job_board_access_url,
)
from persistence import (
    already_applied_to_offer,
    applications_csv,
    control_center_counts,
    init_persistence_tables,
    record_application,
    save_analysis,
)
from services.cv_import import detect_document_kind, extract_docx_text
from services.gdpr_export import export_user_data

ROOT = Path(__file__).resolve().parents[1]


def _paris_profile(**overrides) -> dict:
    profile = {
        "target_job_title": "Développeur Python",
        "contract_type": "CDI",
        "country": "France",
        "selected_countries": ["France"],
        "geo_filter_mode": "departement",
        "admin_regions": ["Île-de-France"],
        "selected_departments": [{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        "selected_cities": ["Paris"],
        "geo_by_country": {
            "France": {
                "admin_regions": ["Île-de-France"],
                "selected_departments": [{"code": "75", "name": "Paris"}],
                "selected_cities": ["Paris"],
                "all_cities": False,
            }
        },
        "experience_level": "tous",
        "target_sectors": [],
        "job_max_age_days": 7,
        "work_mode": "tous",
        "salary_min": 0,
    }
    profile.update(overrides)
    return profile


def _job(title: str, **kwargs) -> dict:
    published_at = (
        datetime.now(timezone.utc) - timedelta(days=kwargs.pop("published_days_ago", 2))
    ).isoformat()
    job = {
        "title": title,
        "location": kwargs.pop("location", "Paris (75), France"),
        "description": kwargs.pop("description", "CDI développeur python"),
        "contract_type": kwargs.pop("contract_type", "CDI"),
        "published_at": published_at,
        "url": kwargs.pop("url", f"https://example.com/{title.replace(' ', '-')}"),
        "company": kwargs.pop("company", "Acme"),
    }
    job.update(kwargs)
    return job


def _minimal_docx(text: str) -> bytes:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    document = ET.Element(f"{{{ns}}}document")
    body = ET.SubElement(document, f"{{{ns}}}body")
    paragraph = ET.SubElement(body, f"{{{ns}}}p")
    run = ET.SubElement(paragraph, f"{{{ns}}}r")
    node = ET.SubElement(run, f"{{{ns}}}t")
    node.text = text
    xml = ET.tostring(document, encoding="utf-8", xml_declaration=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
    return buffer.getvalue()


def _register_jane() -> int:
    ok, msg = register_user(
        "Jane Doe",
        "jane@example.com",
        "Secret123!",
        target_job_title="Developer",
        contract_type="CDI",
        experience_level="confirme",
        selected_countries=["France"],
        admin_regions=["Île-de-France"],
        selected_departments=[{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        selected_cities=["Paris"],
    )
    assert ok, msg
    ok_login, _, user = authenticate_user("jane@example.com", "Secret123!")
    assert ok_login and user is not None
    return int(user["id"])


def test_parse_salary_and_work_mode() -> None:
    assert parse_annual_salary_eur("Rémunération 45k€") == 45000
    assert parse_annual_salary_eur("Salaire 40 000 € - 50 000 €") == 40000
    remote = _job("Dev", location="Full remote, France", description="Télétravail complet CDI python")
    hybrid = _job("Dev", description="CDI python hybride 3 jours remote")
    onsite = _job("Dev", description="CDI python présentiel Paris")
    assert infer_job_work_mode(remote) == "remote"
    assert infer_job_work_mode(hybrid) == "hybrid"
    assert infer_job_work_mode(onsite) == "onsite"
    assert job_matches_work_mode(remote, "remote")
    assert not job_matches_work_mode(onsite, "remote")
    assert job_matches_work_mode(_job("Dev"), "remote")
    paid = _job("Dev", description="CDI python 35k€")
    rich = _job("Dev", description="CDI python 55 000 €")
    assert infer_job_salary_min(paid) == 35000
    assert job_matches_salary(rich, 45000)
    assert not job_matches_salary(paid, 45000)
    assert job_matches_salary(_job("Dev"), 45000)


def test_strict_filters_keep_unknown_salary_and_drop_low_pay() -> None:
    jobs = [
        _job("Paid well", description="CDI python 50 000 €"),
        _job("Paid low", description="CDI python 30k€"),
        _job("No salary", description="CDI python"),
        _job("Remote only", description="CDI python full remote télétravail"),
    ]
    kept, stats = apply_strict_job_filters(
        jobs,
        _paris_profile(work_mode="onsite", salary_min=40000),
    )
    titles = {item["title"] for item in kept}
    assert "Paid well" in titles
    assert "No salary" in titles
    assert "Paid low" not in titles
    assert "Remote only" not in titles
    assert stats["rejected_salary"] == 1
    assert stats["rejected_work_mode"] == 1


def test_docx_import_extracts_paragraphs() -> None:
    payload = _minimal_docx(
        "Jane Doe Développeuse Python Paris " + ("expérience " * 20)
    )
    assert detect_document_kind(payload, "cv.docx") == "docx"
    text = extract_docx_text(payload)
    assert "Développeuse Python" in text


def test_france_travail_and_freelance_are_selectable() -> None:
    assert JOB_PROVIDER_FRANCE_TRAVAIL in JOB_PROVIDER_CHOICES
    assert JOB_PROVIDER_FREELANCE in JOB_PROVIDER_CHOICES
    assert JOB_PROVIDER_SIDEBAR_ORDER[1] == "career_sites"
    assert JOB_PROVIDER_SIDEBAR_ORDER[2] == "wttj"
    available = configured_providers(secrets={"serpapi_api_key": "x"})
    assert JOB_PROVIDER_FRANCE_TRAVAIL in available
    assert JOB_PROVIDER_FREELANCE in available
    assert job_board_access_url(JOB_PROVIDER_FRANCE_TRAVAIL).startswith("https://")
    assert job_board_access_url(JOB_PROVIDER_FREELANCE).startswith("https://")


def test_duplicate_offer_csv_gdpr_and_control_rates(sqlite_db) -> None:
    import persistence

    persistence._persistence_initialized_for = None
    from auth import init_db

    init_db()
    init_persistence_tables()
    user_id = _register_jane()
    job = {
        "title": "Dev Python",
        "company": "Nova",
        "location": "Paris",
        "url": "https://example.com/job-1",
        "description": "CDI",
    }
    analysis_id = save_analysis(
        user_id,
        {
            "cv_text": "CV Jane " * 20,
            "criteria": {},
            "user_profile": {"full_name": "Jane Doe", "email": "jane@example.com"},
            "target_job_title": "Developer",
            "search_plan": {},
            "filter_stats": {},
            "jobs_found": 1,
            "jobs_raw": 1,
            "job_provider": "wttj",
            "results": [{"job": job, "match": {"score_correspondance": 80}}],
        },
        cv_fingerprint="fp-spec",
    )
    from persistence import get_analysis

    stored = get_analysis(user_id, analysis_id)
    assert stored is not None
    result_id = int(stored["results"][0]["result_id"])
    record_application(user_id, result_id, "manual", status="applied")
    assert already_applied_to_offer(user_id, job)
    assert already_applied_to_offer(
        user_id, {"title": "Autre", "url": "https://example.com/job-1", "company": "X"}
    )
    assert already_applied_to_offer(user_id, {"title": "Autre", "url": "https://other.example"}) is None
    csv_text = applications_csv(user_id)
    assert "Dev Python" in csv_text
    assert "Nova" in csv_text
    counts = control_center_counts(user_id)
    assert counts["applied"] >= 1
    assert counts["matching_rate"] >= 0
    ok, message, updated = update_user_profile(
        user_id,
        "Jane Doe",
        "Paris",
        "75001",
        ["Île-de-France"],
        [{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        ["Paris"],
        False,
        "France",
        "CDI",
        "departement",
        20,
        "confirme",
        None,
        "Developer",
        7,
        selected_countries=["France"],
        phone="0600000000",
        work_mode="remote",
        salary_min=45000,
        skills_text="Python, Django",
        diplomas_text="Master info",
        experiences_text="3 ans backend",
        daily_rate=500,
        portfolio_url="https://github.com/jane",
    )
    assert ok, message
    assert updated["work_mode"] == "remote"
    assert updated["salary_min"] == 45000
    assert "Python" in updated["skills_text"]
    payload = export_user_data(updated)
    assert payload["profile"]["email"] == "jane@example.com"
    assert "password" not in json.dumps(payload).lower()
    assert payload["applications"]


def test_freelance_and_followup_templates() -> None:
    job = {"title": "Mission data", "company": "ClientX"}
    profile = {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "skills_text": "Python",
        "daily_rate": 500,
    }
    proposal = generate_freelance_proposal("CV Python Django", job, profile)
    quote = generate_freelance_quote(job, profile, days=8)
    follow = generate_followup_message(job, profile)
    assert "ClientX" in proposal
    assert "500" in quote and "8" in quote
    assert "Mission data" in follow
    assert "Jane Doe" in follow


def test_spec_locale_and_ui_hooks() -> None:
    fr = json.loads((ROOT / "locales/fr.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "locales/en.json").read_text(encoding="utf-8"))
    for key in (
        "profile.work_mode",
        "profile.salary_min",
        "profile.freelance_locked_help",
        "profile.gdpr_export",
        "notify.daily_limit",
        "job.freelance_proposal",
        "job.apply_duplicate_offer",
        "provider.france_travail",
        "applications.export_csv",
        "overview.kpi_matching",
    ):
        assert fr[key].strip(), key
        assert en[key].strip(), key
    assert "ne postule pas" in fr["notify.daily_limit_help"].lower()
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "already_applied_to_offer" in source
    assert 'type=["pdf", "docx"]' in source
    assert "generate_freelance_proposal" in source
    assert "export_user_data" in source
    assert "applications_csv" in source
    assert "JOB_PROVIDER_FRANCE_TRAVAIL" in source
