"""Apply click must not tear Streamlit DOM nodes (removeChild)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_chat_fab_never_removes_parent_nodes() -> None:
    app = _read("app.py")
    fab_fn = app.split("def render_floating_chat_fab")[1].split("def render_history_page")[0]
    assert ".remove()" not in fab_fn
    assert "display = \"none\"" in fab_fn
    assert "catch (err)" in fab_fn


def test_auto_apply_is_deferred_off_the_clicked_button() -> None:
    source = _read("app.py")
    start = source.index("def _render_apply_action_buttons(")
    end = source.index("def _format_job_salary(", start)
    body = source[start:end]
    assert "_pending_auto_apply" in body
    assert "on_click" in body
    assert "_queue_pending_auto_apply" in body
    assert body.index("_pending_auto_apply") < body.index("st.button(")
    assert "_run_auto_apply_action(" in body.split("st.button(")[0]


def test_simple_row_uses_expander_instead_of_rerun_toggle() -> None:
    source = _read("app.py")
    start = source.index("def render_simple_job_row(")
    end = source.index("def render_job_card(", start)
    body = source[start:end]
    assert 'st.expander(t("job.analyze_offer")' in body
    assert "st.rerun()" not in body
    assert 'key=f"toggle_{details_key}"' not in body
