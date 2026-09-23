"""Each registration step must be complete before Next / Submit."""

from __future__ import annotations


class _State(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: object) -> None:
        self[name] = value


def _bind_state(monkeypatch, **values):
    import app as app_mod

    state = _State(values)
    monkeypatch.setattr(app_mod.st, "session_state", state)
    return app_mod, state


def test_language_step_requires_supported_locale(monkeypatch):
    app_mod, _state = _bind_state(monkeypatch)
    ok, message = app_mod._validate_register_wizard_step(0)
    assert ok is False
    assert message
    _state["register_wiz_locale"] = "fr"
    assert app_mod._validate_register_wizard_step(0)[0] is True


def test_country_step_requires_explicit_selection(monkeypatch):
    app_mod, state = _bind_state(monkeypatch)
    assert app_mod._validate_register_wizard_step(1)[0] is False
    state["register_selected_countries"] = ["France"]
    assert app_mod._validate_register_wizard_step(1)[0] is True


def test_identity_step_requires_phone_and_matching_password(monkeypatch):
    app_mod, state = _bind_state(
        monkeypatch,
        register_wiz_first_name="Jean",
        register_wiz_last_name="Dupont",
        register_wiz_email="jean@test.fr",
        register_wiz_phone="",
        register_wiz_password="Secret123!",
        register_wiz_password2="Secret123!",
    )
    ok, message = app_mod._validate_register_wizard_step(2)
    assert ok is False
    assert "téléphone" in message.lower() or "phone" in message.lower()
    state["register_wiz_phone"] = "+33 6 12 34 56 78"
    assert app_mod._validate_register_wizard_step(2)[0] is True
    state["register_wiz_password2"] = "Other123!"
    assert app_mod._validate_register_wizard_step(2)[0] is False


def test_job_step_requires_title(monkeypatch):
    app_mod, state = _bind_state(monkeypatch)
    assert app_mod._validate_register_wizard_step(3)[0] is False
    state["register_wiz_target_job"] = "Développeur Python"
    assert app_mod._validate_register_wizard_step(3)[0] is True


def test_location_step_requires_france_geo(monkeypatch):
    app_mod, state = _bind_state(monkeypatch, register_selected_countries=["France"])
    assert app_mod._validate_register_wizard_step(4)[0] is False
    incomplete = {
        "admin_regions": ["Île-de-France"],
        "departments": [],
        "cities": [],
        "all_cities": False,
        "geo_by_country": {},
    }
    assert app_mod._validate_register_wizard_step(4, geo=incomplete)[0] is False
    complete = {
        "admin_regions": ["Île-de-France"],
        "departments": [{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        "cities": ["Paris"],
        "all_cities": False,
        "geo_by_country": {},
    }
    assert app_mod._validate_register_wizard_step(4, geo=complete)[0] is True


def test_preferences_step_requires_sector(monkeypatch):
    app_mod, state = _bind_state(
        monkeypatch,
        register_wiz_contract="CDI",
        register_wiz_experience="confirme",
        register_target_sectors=[],
        register_wiz_publication_age=7,
    )
    assert app_mod._validate_register_wizard_step(5)[0] is False
    state["register_target_sectors"] = ["Informatique"]
    assert app_mod._validate_register_wizard_step(5)[0] is True


def test_complete_wizard_checks_every_step(monkeypatch):
    app_mod, _state = _bind_state(
        monkeypatch,
        register_wiz_locale="fr",
        register_selected_countries=["France"],
        register_wiz_first_name="Jean",
        register_wiz_last_name="Dupont",
        register_wiz_email="jean@test.fr",
        register_wiz_phone="+33612345678",
        register_wiz_password="Secret123!",
        register_wiz_password2="Secret123!",
        register_wiz_target_job="Dev",
        register_wiz_contract="CDI",
        register_wiz_experience="confirme",
        register_target_sectors=["Informatique"],
        register_wiz_publication_age=7,
    )
    geo = {
        "admin_regions": ["Île-de-France"],
        "departments": [{"code": "75", "name": "Paris", "region": "Île-de-France"}],
        "cities": ["Paris"],
        "all_cities": False,
        "geo_by_country": {},
    }
    assert app_mod._validate_register_wizard_complete(geo)[0] is True
    _state["register_wiz_phone"] = ""
    assert app_mod._validate_register_wizard_complete(geo)[0] is False
