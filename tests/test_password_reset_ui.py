"""Reset form hides the new password until the e-mailed code is verified."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reset_form_is_a_three_step_code_flow():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    fn = source[
        source.index("def _render_auth_reset_form()") : source.index("REGISTER_WIZARD_STEPS")
    ]
    assert "request_password_reset_code" in fn
    assert "verify_password_reset_code" in fn
    assert "complete_verified_password_reset" in fn
    assert 'st.form("reset_form"' not in source
    assert 'key="reset_send_code"' in fn
    assert 'key="reset_verify_code"' in fn
    assert 'key="reset_submit_password"' in fn
    identify_end = fn.index('return')
    assert 'key="reset_password_1"' not in fn[:identify_end]
    code_end = fn.index('return', identify_end + 1)
    assert 'key="reset_password_1"' not in fn[:code_end]
    assert 'key="reset_password_2"' not in fn[:code_end]
    password_idx = fn.index('key="reset_password_1"')
    verify_idx = fn.index("verify_password_reset_code")
    assert verify_idx < password_idx
    assert 'step not in {"identify", "code", "password"}' in fn
    assert 'key="reset_submit_password"' in fn[password_idx:]
    assert "_store_reset_identity" in fn
    assert "_reset_identity_email()" in fn
    code_step = fn[fn.index("if step == \"code\"") :]
    assert 'st.session_state.get("reset_email", "")' not in code_step


def test_reset_code_locale_keys_exist():
    for locale in ("fr", "en"):
        data = json.loads((ROOT / f"locales/{locale}.json").read_text(encoding="utf-8"))
        for key in (
            "auth.reset.send_code",
            "auth.reset.verify_code",
            "auth.reset.code_sent",
            "auth.reset.code_invalid",
            "auth.reset.code_expired",
            "email.reset_code_subject",
            "email.reset_code_ttl",
        ):
            assert data[key]
