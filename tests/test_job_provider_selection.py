"""Users can pick two, three or more job-search engines."""

from __future__ import annotations

from pathlib import Path

from job_providers import (
    JOB_PROVIDER_ADZUNA,
    JOB_PROVIDER_ALL,
    JOB_PROVIDER_CAREER_SITES,
    JOB_PROVIDER_CHOICES,
    JOB_PROVIDER_WTTJ,
    encode_job_providers,
    parse_job_providers,
    selected_job_providers,
    uses_provider_fusion,
)

ROOT = Path(__file__).resolve().parents[1]


def test_parse_and_encode_multiple_job_providers() -> None:
    assert parse_job_providers("wttj,adzuna") == [JOB_PROVIDER_WTTJ, JOB_PROVIDER_ADZUNA]
    assert parse_job_providers("adzuna, wttj, career_sites") == [
        JOB_PROVIDER_CAREER_SITES,
        JOB_PROVIDER_WTTJ,
        JOB_PROVIDER_ADZUNA,
    ]
    assert parse_job_providers("all") == [JOB_PROVIDER_ALL]
    assert encode_job_providers([JOB_PROVIDER_WTTJ, JOB_PROVIDER_ADZUNA]) == "wttj,adzuna"
    assert encode_job_providers(list(JOB_PROVIDER_CHOICES)) == JOB_PROVIDER_ALL
    assert uses_provider_fusion("wttj,adzuna")
    assert uses_provider_fusion("all")
    assert not uses_provider_fusion("wttj")


def test_selected_job_providers_keeps_subset_and_can_drop_career() -> None:
    subset = selected_job_providers("career_sites,wttj,adzuna")
    assert subset[:2] == [JOB_PROVIDER_CAREER_SITES, JOB_PROVIDER_WTTJ]
    boards = selected_job_providers("career_sites,wttj,adzuna", include_career=False)
    assert JOB_PROVIDER_CAREER_SITES not in boards
    assert boards == [JOB_PROVIDER_WTTJ, JOB_PROVIDER_ADZUNA]
    career_only = selected_job_providers("career_sites", include_career=False)
    assert career_only == []


def test_sidebar_uses_dropdown_for_job_engines() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    render_app = source.split("def render_app()", 1)[1].split("def main()", 1)[0]
    assert "st.multiselect(" not in render_app
    assert "render_job_provider_picker(" in render_app
    assert 'key="sidebar_job_providers"' in source
    analysis_block = render_app.split('if page == "analysis":', 1)[1].split(
        "render_language_selector", 1
    )[0]
    assert "render_job_provider_picker(" in analysis_block
    assert "st.popover(" in source
    assert "st.checkbox(" in source.split("def render_job_provider_picker", 1)[1].split(
        "def render_app()", 1
    )[0]
    assert 'key="sidebar_job_provider"' not in analysis_block
    assert "parse_job_providers(" in source
    assert "encode_job_providers(" in source
    assert "uses_provider_fusion(" in source
    locales_fr = (ROOT / "locales/fr.json").read_text(encoding="utf-8")
    theme = (ROOT / "ui/theme.py").read_text(encoding="utf-8")
    assert "app.job_provider_empty" in locales_fr
    assert "app.job_provider_summary" in locales_fr
    assert "deux, trois ou plusieurs" in locales_fr
    assert ".sidebar-field-label" in theme
    assert ".st-key-sidebar_job_providers" in theme


def test_job_provider_picker_renders_dropdown_not_chips() -> None:
    from streamlit.testing.v1 import AppTest

    script = """
from app import render_job_provider_picker
from i18n import set_locale
set_locale("fr")
render_job_provider_picker("career_sites,wttj,adzuna")
"""
    at = AppTest.from_string(script)
    at.run()
    assert not at.exception
    assert not at.multiselect
    labels = [box.label for box in at.checkbox]
    assert "Sites carrière" in labels
    assert "Welcome to the Jungle" in labels
    assert "Adzuna" in labels
    assert all("Apify" not in label for label in labels)


def test_job_provider_menu_labels_are_short() -> None:
    from i18n import job_provider_menu_label, set_locale

    set_locale("fr")
    assert job_provider_menu_label("hellowork") == "HelloWork"
    assert job_provider_menu_label("career_sites") == "Sites carrière"
    assert "Apify" not in job_provider_menu_label("jobteaser")
