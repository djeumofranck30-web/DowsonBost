"""Session helpers so saved profile widgets are not wiped on rerun."""

from __future__ import annotations

from typing import Any


def seed_session_value(state: dict[str, Any], key: str, value: Any) -> Any:
    """Set a widget default once; later reruns keep the user's current value."""
    if key not in state:
        state[key] = value
    return state[key]


def retain_multiselect_session(
    state: dict[str, Any],
    *,
    values_key: str,
    signature_key: str,
    current_signature: Any,
    seed_values: list[Any],
    allowed: list[Any] | None = None,
) -> list[Any]:
    """Keep saved multiselect values until the parent filter actually changes.

    Streamlit widgets live in session_state. A missing parent-filter signature
    used to be treated as a change, which replaced the seeded profile values
    with an empty list on the first profile page load (and a later Save then
    wrote that empty geo back to the database).
    """
    allowed_list = list(allowed) if allowed is not None else None
    if values_key not in state:
        values = list(seed_values)
        if allowed_list:
            filtered = [item for item in values if item in allowed_list]
            state[values_key] = filtered or values
        else:
            state[values_key] = values
    if signature_key not in state:
        state[signature_key] = current_signature
        return list(state.get(values_key) or [])
    if state.get(signature_key) != current_signature:
        previous = list(state.get(values_key) or [])
        if allowed_list is not None:
            state[values_key] = [item for item in previous if item in allowed_list]
        state[signature_key] = current_signature
    return list(state.get(values_key) or [])


def profile_widget_prefix(user_id: int) -> str:
    return f"profile_{int(user_id)}"


def clear_profile_widget_keys(state: dict[str, Any], user_id: int) -> None:
    """Drop profile widget keys so the next render reseeds from the database."""
    prefix = profile_widget_prefix(user_id)
    extra = {
        f"profile_first_name_{user_id}",
        f"profile_last_name_{user_id}",
        f"profile_phone_{user_id}",
        f"profile_email_{user_id}",
        f"profile_sectors_{user_id}",
    }
    stale = [
        key
        for key in list(state.keys())
        if key == prefix or str(key).startswith(f"{prefix}_") or key in extra
    ]
    for key in stale:
        state.pop(key, None)
