"""User authentication for DowsonBost — SQLite (local) or PostgreSQL (production)."""

from __future__ import annotations

import hashlib
import re
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

import bcrypt

from constants import PASSWORD_RESET_TOKEN_TTL_HOURS
from database import adapt_sql, connect, database_backend, existing_columns, is_unique_violation
from i18n import normalize_locale, t
from france_geo import (
    parse_admin_regions,
    parse_selected_cities,
    parse_selected_departments,
    profile_all_cities,
    resolve_selected_cities,
    serialize_admin_regions,
    serialize_selected_cities,
    serialize_selected_departments,
)
from job_filters import (
    CONTRACT_TYPES,
    EXPERIENCE_LEVELS,
    GEO_FILTER_MODES,
    SECTOR_OPTIONS,
    normalize_contract_type,
    normalize_experience_level,
    normalize_job_max_age_days,
    parse_target_sectors,
    serialize_target_sectors,
)
from world_geo import (
    COUNTRY_OPTIONS,
    merge_profile_geo,
    normalize_country_name,
    parse_geo_by_country,
    parse_selected_countries,
    profile_countries,
    profile_primary_country,
    serialize_geo_by_country,
    serialize_selected_countries,
    sync_france_legacy_fields,
    validate_profile_countries_geo,
)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
POSTAL_CODE_PATTERN = re.compile(r"^\d{4,5}$")
MIN_PASSWORD_LENGTH = 8

_USER_COLUMNS = [
    ("home_city", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ("postal_code", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ("region", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ("contract_type", "TEXT NOT NULL DEFAULT 'CDI'", "TEXT NOT NULL DEFAULT 'CDI'"),
    ("search_radius_km", "INTEGER NOT NULL DEFAULT 20", "INTEGER NOT NULL DEFAULT 20"),
    ("geo_filter_mode", "TEXT NOT NULL DEFAULT 'departement'", "TEXT NOT NULL DEFAULT 'departement'"),
    ("experience_level", "TEXT NOT NULL DEFAULT 'confirme'", "TEXT NOT NULL DEFAULT 'confirme'"),
    ("target_sectors", "TEXT NOT NULL DEFAULT '[]'", "TEXT NOT NULL DEFAULT '[]'"),
    ("admin_region", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ("department_code", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ("department_name", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ("country", "TEXT NOT NULL DEFAULT 'France'", "TEXT NOT NULL DEFAULT 'France'"),
    ("admin_regions", "TEXT NOT NULL DEFAULT '[]'", "TEXT NOT NULL DEFAULT '[]'"),
    ("selected_departments", "TEXT NOT NULL DEFAULT '[]'", "TEXT NOT NULL DEFAULT '[]'"),
    ("selected_cities", "TEXT NOT NULL DEFAULT '[]'", "TEXT NOT NULL DEFAULT '[]'"),
    ("all_cities", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
    ("selected_countries", "TEXT NOT NULL DEFAULT '[\"France\"]'", "TEXT NOT NULL DEFAULT '[\"France\"]'"),
    ("geo_by_country", "TEXT NOT NULL DEFAULT '{}'", "TEXT NOT NULL DEFAULT '{}'"),
    ("target_job_title", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ("job_max_age_days", "INTEGER NOT NULL DEFAULT 7", "INTEGER NOT NULL DEFAULT 7"),
    ("preferred_language", "TEXT NOT NULL DEFAULT 'fr'", "TEXT NOT NULL DEFAULT 'fr'"),
    ("phone", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ("is_admin", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
    ("last_login_at", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
]


def split_full_name(full_name: str) -> tuple[str, str]:
    """Split stored full name into first and last name."""
    normalized = " ".join((full_name or "").split())
    if not normalized:
        return "", ""
    parts = normalized.split(" ", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def join_full_name(first_name: str, last_name: str) -> str:
    """Combine first and last name for storage."""
    return " ".join(f"{first_name} {last_name}".split())


@contextmanager
def _connect() -> Iterator[Any]:
    with connect() as conn:
        yield conn


def _create_users_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                home_city TEXT NOT NULL DEFAULT '',
                postal_code TEXT NOT NULL DEFAULT '',
                region TEXT NOT NULL DEFAULT '',
                contract_type TEXT NOT NULL DEFAULT 'CDI',
                search_radius_km INTEGER NOT NULL DEFAULT 20,
                geo_filter_mode TEXT NOT NULL DEFAULT 'departement',
                experience_level TEXT NOT NULL DEFAULT 'confirme',
                target_sectors TEXT NOT NULL DEFAULT '[]',
                admin_region TEXT NOT NULL DEFAULT '',
                department_code TEXT NOT NULL DEFAULT '',
                department_name TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT 'France',
                admin_regions TEXT NOT NULL DEFAULT '[]',
                selected_departments TEXT NOT NULL DEFAULT '[]',
                selected_cities TEXT NOT NULL DEFAULT '[]',
                all_cities INTEGER NOT NULL DEFAULT 0,
                target_job_title TEXT NOT NULL DEFAULT '',
                job_max_age_days INTEGER NOT NULL DEFAULT 7
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_idx
            ON users (LOWER(email))
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            home_city TEXT NOT NULL DEFAULT '',
            postal_code TEXT NOT NULL DEFAULT '',
            region TEXT NOT NULL DEFAULT '',
            contract_type TEXT NOT NULL DEFAULT 'CDI',
            search_radius_km INTEGER NOT NULL DEFAULT 20,
            geo_filter_mode TEXT NOT NULL DEFAULT 'departement',
            experience_level TEXT NOT NULL DEFAULT 'confirme',
            target_sectors TEXT NOT NULL DEFAULT '[]',
            admin_region TEXT NOT NULL DEFAULT '',
            department_code TEXT NOT NULL DEFAULT '',
            department_name TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL DEFAULT 'France',
            admin_regions TEXT NOT NULL DEFAULT '[]',
            selected_departments TEXT NOT NULL DEFAULT '[]',
            selected_cities TEXT NOT NULL DEFAULT '[]',
            all_cities INTEGER NOT NULL DEFAULT 0,
            target_job_title TEXT NOT NULL DEFAULT '',
            job_max_age_days INTEGER NOT NULL DEFAULT 7
        )
        """
    )


def _migrate_users(conn: Any) -> None:
    """Add profile columns for job matching preferences."""
    cols = existing_columns(conn)
    for column, sqlite_type, postgres_type in _USER_COLUMNS:
        if column in cols:
            continue
        typedef = postgres_type if database_backend() == "postgres" else sqlite_type
        if database_backend() == "postgres":
            conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column} {typedef}")
        else:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} {typedef}")

    _migrate_legacy_geo_to_multi(conn)
    _migrate_legacy_cities(conn)


def _migrate_legacy_cities(conn: Any) -> None:
    """Copy home_city into selected_cities when the list is empty."""
    rows = conn.execute(
        adapt_sql("SELECT id, home_city, selected_cities FROM users")
    ).fetchall()
    for row in rows:
        cities = parse_selected_cities(row["selected_cities"])
        if cities:
            continue
        home = (row["home_city"] or "").strip()
        if home:
            conn.execute(
                adapt_sql("UPDATE users SET selected_cities = ? WHERE id = ?"),
                (serialize_selected_cities([home]), row["id"]),
            )


def _migrate_legacy_geo_to_multi(conn: Any) -> None:
    """Copy single region/department into JSON lists when lists are empty."""
    rows = conn.execute(
        adapt_sql(
            """
            SELECT id, admin_region, region, department_code, department_name,
                   admin_regions, selected_departments
            FROM users
            """
        )
    ).fetchall()
    for row in rows:
        regions = parse_admin_regions(row["admin_regions"])
        departments = parse_selected_departments(row["selected_departments"])
        if regions and departments:
            continue

        legacy_region = (row["admin_region"] or row["region"] or "").strip()
        legacy_code = (row["department_code"] or "").strip().upper()
        legacy_name = (row["department_name"] or "").strip()

        if not regions and legacy_region:
            regions = [legacy_region]
        if not departments and legacy_code:
            departments = [
                {
                    "code": legacy_code,
                    "name": legacy_name,
                    "region": legacy_region or regions[0] if regions else "",
                }
            ]

        if regions or departments:
            conn.execute(
                adapt_sql(
                    """
                    UPDATE users
                    SET admin_regions = ?, selected_departments = ?
                    WHERE id = ?
                    """
                ),
                (
                    serialize_admin_regions(regions),
                    serialize_selected_departments(departments),
                    row["id"],
                ),
            )


_DB_SCHEMA_KEY: tuple[str, ...] = tuple(col[0] for col in _USER_COLUMNS)
_db_initialized_for: tuple[str, ...] | None = None


def _create_password_reset_tokens_table(conn: Any) -> None:
    if database_backend() == "postgres":
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS password_reset_tokens_user_idx
            ON password_reset_tokens (user_id)
            """
        )
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS password_reset_tokens_user_idx
        ON password_reset_tokens (user_id)
        """
    )


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_reset_token(email: str) -> tuple[bool, str, str]:
    """Create a single-use password reset token for a registered e-mail."""
    email = email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        return False, t("auth.email.invalid"), ""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql("SELECT id FROM users WHERE email = ?"),
            (email,),
        ).fetchone()
    if not row:
        return False, t("auth.reset.not_found"), ""

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=PASSWORD_RESET_TOKEN_TTL_HOURS)
    with _connect() as conn:
        conn.execute(
            adapt_sql(
                """
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """
            ),
            (
                int(row["id"]),
                _hash_reset_token(token),
                expires.isoformat(),
                now.isoformat(),
            ),
        )
    return True, t("auth.reset.token_created"), token


def reset_password_with_token(token: str, new_password: str) -> tuple[bool, str]:
    """Reset password using a valid e-mail token."""
    token = token.strip()
    new_password = new_password.strip()
    valid_pw, pw_msg = _validate_password(new_password)
    if not valid_pw:
        return False, pw_msg
    if not token:
        return False, t("auth.reset.token_invalid")

    init_db()
    token_hash = _hash_reset_token(token)
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql(
                """
                SELECT id, user_id, expires_at, used_at
                FROM password_reset_tokens
                WHERE token_hash = ?
                """
            ),
            (token_hash,),
        ).fetchone()
        if not row:
            return False, t("auth.reset.token_invalid")
        if row["used_at"]:
            return False, t("auth.reset.token_used")
        if str(row["expires_at"]) < now:
            return False, t("auth.reset.token_expired")
        conn.execute(
            adapt_sql("UPDATE users SET password_hash = ? WHERE id = ?"),
            (_hash_password(new_password), int(row["user_id"])),
        )
        conn.execute(
            adapt_sql("UPDATE password_reset_tokens SET used_at = ? WHERE id = ?"),
            (now, int(row["id"])),
        )
    return True, t("auth.reset.success")


def request_password_reset_email(email: str) -> tuple[bool, str]:
    """Create a reset token and send the recovery link by e-mail when configured."""
    ok, message, token = create_password_reset_token(email)
    if not ok or not token:
        return ok, message

    from config import get_app_base_url
    from email_service import send_password_reset_email

    reset_url = f"{get_app_base_url()}/?reset_token={token}"
    sent, send_msg = send_password_reset_email(email, reset_url)
    if sent:
        return True, t("auth.reset.email_sent")
    return True, message


def init_db() -> None:
    """Create users table if it does not exist (once per process / schema version)."""
    global _db_initialized_for
    if _db_initialized_for == _DB_SCHEMA_KEY:
        return
    with _connect() as conn:
        _create_users_table(conn)
        _migrate_users(conn)
        _create_password_reset_tokens_table(conn)
    from persistence import init_persistence_tables

    init_persistence_tables()
    try:
        from migrations.runner import run_migrations

        run_migrations()
    except Exception:  # noqa: BLE001 — migrations optional on first boot
        pass
    _db_initialized_for = _DB_SCHEMA_KEY


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _validate_password(password: str) -> tuple[bool, str]:
    if len(password.strip()) < MIN_PASSWORD_LENGTH:
        return False, t("auth.password.min", min=MIN_PASSWORD_LENGTH)
    return True, ""


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


def _validate_profile_fields(
    home_city: str,
    postal_code: str,
    contract_type: str,
    geo_filter_mode: str,
    search_radius_km: int,
    experience_level: str = "confirme",
    target_sectors: list[str] | None = None,
    admin_regions: list[str] | None = None,
    selected_departments: list[dict[str, str]] | None = None,
    selected_cities: list[str] | None = None,
    all_cities: bool = False,
    admin_region: str = "",
    department_code: str = "",
    target_job_title: str = "",
    selected_countries: list[str] | None = None,
    geo_by_country: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    title = " ".join(target_job_title.strip().split())
    if len(title) < 2:
        return False, t("auth.validation.job_title")
    if home_city.strip() and len(home_city.strip()) < 2:
        return False, t("auth.validation.home_city")
    postal = postal_code.strip()
    if postal and not POSTAL_CODE_PATTERN.match(postal):
        return False, t("auth.validation.postal")

    countries = [
        normalize_country_name(c)
        for c in (selected_countries or ["France"])
        if str(c).strip()
    ]
    geo_map = geo_by_country or {}
    if geo_map and countries:
        ok, msg = validate_profile_countries_geo(countries, geo_map)
        if not ok:
            return False, msg
    elif "France" in countries or not countries:
        regions = admin_regions or []
        if not regions and admin_region.strip():
            regions = [admin_region.strip()]
        if not regions:
            return False, t("auth.validation.region_fr")

        departments = selected_departments or []
        if not departments and department_code.strip():
            departments = [{"code": department_code.strip().upper(), "name": "", "region": regions[0]}]
        if not departments:
            return False, t("auth.validation.dept_fr")

        cities = selected_cities or []
        if not all_cities:
            if not cities:
                cities = resolve_selected_cities({"home_city": home_city, "selected_cities": []})
            if not cities:
                return False, t("auth.validation.city_fr")
    normalized_contract = normalize_contract_type(contract_type)
    if normalized_contract not in CONTRACT_TYPES:
        return False, t("auth.validation.contract")
    if geo_filter_mode not in GEO_FILTER_MODES:
        return False, t("auth.validation.geo_mode")
    if search_radius_km < 5 or search_radius_km > 200:
        return False, t("auth.validation.radius")
    level = normalize_experience_level(experience_level)
    if level not in EXPERIENCE_LEVELS:
        return False, t("auth.validation.experience")
    if target_sectors:
        invalid = [s for s in target_sectors if s not in SECTOR_OPTIONS]
        if invalid:
            return False, t("auth.validation.sectors", sectors=", ".join(invalid))
    return True, ""


_USER_SELECT_SQL = """
    id, full_name, email, created_at, home_city, postal_code, region,
    admin_region, department_code, department_name,
    contract_type, search_radius_km, geo_filter_mode,
    experience_level, target_sectors, country,
    admin_regions, selected_departments, selected_cities, all_cities,
    selected_countries, geo_by_country,
    target_job_title, job_max_age_days, preferred_language, phone,
    is_admin, last_login_at
"""


def _legacy_geo_from_lists(
    admin_regions: list[str],
    selected_departments: list[dict[str, str]],
) -> tuple[str, str, str]:
    admin_region = admin_regions[0] if admin_regions else ""
    if selected_departments:
        return (
            admin_region,
            selected_departments[0].get("code", ""),
            selected_departments[0].get("name", ""),
        )
    return admin_region, "", ""


def _row_has(row: Any, key: str) -> bool:
    try:
        return key in row.keys()
    except Exception:  # noqa: BLE001
        try:
            return key in row
        except Exception:  # noqa: BLE001
            return False


def _row_text(row: Any, key: str) -> str:
    if not _row_has(row, key):
        return ""
    value = row[key]
    return str(value or "").strip()


def _row_flag(row: Any, key: str) -> bool:
    if not _row_has(row, key):
        return False
    value = row[key]
    if isinstance(value, bool):
        return value
    try:
        return int(value or 0) == 1
    except (TypeError, ValueError):
        return bool(value)


def user_is_admin(user: dict[str, Any] | None) -> bool:
    """True when the account is flagged admin or listed in ADMIN_EMAILS."""
    if not user:
        return False
    if user.get("is_admin"):
        return True
    email = str(user.get("email") or "").strip().lower()
    if not email:
        return False
    from config import get_admin_emails

    return email in get_admin_emails()


def _row_to_user(row: Any, include_created: bool = False) -> dict:
    admin_regions = parse_admin_regions(row["admin_regions"])
    selected_departments = parse_selected_departments(row["selected_departments"])
    legacy_region = row["admin_region"] or row["region"]
    if not admin_regions and legacy_region:
        admin_regions = [legacy_region]
    if not selected_departments and row["department_code"]:
        selected_departments = [
            {
                "code": row["department_code"],
                "name": row["department_name"],
                "region": admin_regions[0] if admin_regions else legacy_region,
            }
        ]

    admin_region, department_code, department_name = _legacy_geo_from_lists(
        admin_regions, selected_departments
    )
    selected_cities = parse_selected_cities(row["selected_cities"])
    all_cities = profile_all_cities({"all_cities": row["all_cities"]})
    if not selected_cities and not all_cities and row["home_city"]:
        selected_cities = [row["home_city"]]
    user = {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "home_city": row["home_city"],
        "postal_code": row["postal_code"],
        "region": admin_region,
        "admin_region": admin_region,
        "admin_regions": admin_regions,
        "department_code": department_code,
        "department_name": department_name,
        "selected_departments": selected_departments,
        "selected_cities": selected_cities,
        "all_cities": all_cities,
        "country": row["country"] or "France",
        "contract_type": row["contract_type"],
        "search_radius_km": row["search_radius_km"],
        "geo_filter_mode": row["geo_filter_mode"],
        "experience_level": row["experience_level"],
        "target_sectors": parse_target_sectors(row["target_sectors"]),
        "target_job_title": (row["target_job_title"] or "").strip(),
        "job_max_age_days": normalize_job_max_age_days(
            row["job_max_age_days"] if "job_max_age_days" in row.keys() else 7
        ),
        "selected_countries": parse_selected_countries(
            row["selected_countries"] if "selected_countries" in row.keys() else None,
            fallback_country=row["country"] or "France",
        ),
        "geo_by_country": merge_profile_geo(
            {
                "country": row["country"] or "France",
                "selected_countries": row["selected_countries"]
                if "selected_countries" in row.keys()
                else None,
                "geo_by_country": row["geo_by_country"]
                if "geo_by_country" in row.keys()
                else {},
                "admin_regions": admin_regions,
                "selected_departments": selected_departments,
                "selected_cities": selected_cities,
                "all_cities": all_cities,
            }
        ),
        "preferred_language": normalize_locale(
            row["preferred_language"] if "preferred_language" in row.keys() else "fr"
        ),
        "phone": (row["phone"] or "").strip() if "phone" in row.keys() else "",
        "is_admin": _row_flag(row, "is_admin"),
        "last_login_at": _row_text(row, "last_login_at"),
    }
    if include_created:
        user["created_at"] = row["created_at"]
    return user


def get_user_by_id(user_id: int) -> dict | None:
    """Return user profile including job-matching preferences."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql(
                f"""
                SELECT {_USER_SELECT_SQL}
                FROM users WHERE id = ?
                """
            ),
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return _row_to_user(row, include_created=True)


def register_user(
    full_name: str,
    email: str,
    password: str,
    home_city: str = "",
    postal_code: str = "",
    admin_regions: list[str] | None = None,
    selected_departments: list[dict[str, str]] | None = None,
    selected_cities: list[str] | None = None,
    all_cities: bool = False,
    admin_region: str = "",
    department_code: str = "",
    department_name: str = "",
    country: str = "France",
    contract_type: str = "CDI",
    geo_filter_mode: str = "departement",
    search_radius_km: int = 20,
    experience_level: str = "confirme",
    target_sectors: list[str] | None = None,
    target_job_title: str = "",
    job_max_age_days: int = 7,
    selected_countries: list[str] | None = None,
    geo_by_country: dict[str, dict[str, Any]] | None = None,
    preferred_language: str = "fr",
    phone: str = "",
) -> tuple[bool, str]:
    """Register a new user. Returns (success, message)."""
    full_name = " ".join(full_name.strip().split())
    email = email.strip().lower()
    password = password.strip()
    home_city = " ".join(home_city.strip().split())
    regions = [r.strip() for r in (admin_regions or []) if r.strip()]
    if not regions and admin_region.strip():
        regions = [" ".join(admin_region.strip().split())]
    departments = selected_departments or []
    if not departments and department_code.strip():
        departments = [
            {
                "code": department_code.strip().upper(),
                "name": " ".join(department_name.strip().split()),
                "region": regions[0] if regions else "",
            }
        ]
    admin_region, department_code, department_name = _legacy_geo_from_lists(
        regions, departments
    )
    cities = [c.strip() for c in (selected_cities or []) if c.strip()]
    if not all_cities and not cities and home_city:
        cities = [home_city]
    if all_cities:
        cities = []
    countries = [
        normalize_country_name(c)
        for c in (selected_countries or [country.strip() or "France"])
        if str(c).strip()
    ]
    geo_map = dict(geo_by_country or {})
    if "France" in countries:
        from world_geo import france_geo_from_profile

        geo_map["France"] = france_geo_from_profile(
            {
                "admin_regions": regions,
                "selected_departments": departments,
                "selected_cities": cities,
                "all_cities": all_cities,
            }
        )
    country = countries[0] if countries else "France"
    contract_type = normalize_contract_type(contract_type)
    geo_filter_mode = geo_filter_mode.strip().lower()
    experience_level = normalize_experience_level(experience_level)
    sectors = target_sectors or []
    job_title = " ".join(target_job_title.strip().split())
    publication_days = normalize_job_max_age_days(job_max_age_days)
    language = normalize_locale(preferred_language)
    phone_clean = " ".join(phone.strip().split())

    if len(full_name) < 2:
        return False, t("auth.name.min")
    if not EMAIL_PATTERN.match(email):
        return False, t("auth.email.invalid")

    valid_pw, pw_msg = _validate_password(password)
    if not valid_pw:
        return False, pw_msg

    valid_profile, profile_msg = _validate_profile_fields(
        home_city,
        postal_code,
        contract_type,
        geo_filter_mode,
        search_radius_km,
        experience_level,
        sectors,
        admin_regions=regions,
        selected_departments=departments,
        selected_cities=cities,
        all_cities=all_cities,
        target_job_title=job_title,
        selected_countries=countries,
        geo_by_country=geo_map,
    )
    if not valid_profile:
        return False, profile_msg

    init_db()
    try:
        with _connect() as conn:
            conn.execute(
                adapt_sql(
                    """
                    INSERT INTO users (
                        full_name, email, password_hash, created_at,
                        home_city, postal_code, region, admin_region,
                        department_code, department_name, contract_type,
                        search_radius_km, geo_filter_mode, experience_level, target_sectors,
                        country, admin_regions, selected_departments, selected_cities, all_cities,
                        selected_countries, geo_by_country,
                        target_job_title, job_max_age_days, preferred_language, phone
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    full_name,
                    email,
                    _hash_password(password),
                    datetime.now(timezone.utc).isoformat(),
                    home_city,
                    postal_code.strip(),
                    admin_region,
                    admin_region,
                    department_code,
                    department_name,
                    contract_type,
                    search_radius_km,
                    geo_filter_mode,
                    experience_level,
                    serialize_target_sectors(sectors),
                    country,
                    serialize_admin_regions(regions),
                    serialize_selected_departments(departments),
                    serialize_selected_cities(cities),
                    1 if all_cities else 0,
                    serialize_selected_countries(countries),
                    serialize_geo_by_country(geo_map),
                    job_title,
                    publication_days,
                    language,
                    phone_clean,
                ),
            )
    except Exception as exc:  # noqa: BLE001
        if is_unique_violation(exc):
            return False, t("auth.register.email_exists")
        raise

    sent = False
    try:
        from config import get_app_base_url
        from email_service import send_welcome_email

        login_url = f"{get_app_base_url()}/"
        sent, _ = send_welcome_email(email, full_name, login_url, locale=language)
    except Exception:  # noqa: BLE001 — registration must succeed even if mail fails
        sent = False
    if sent:
        return True, t("auth.register.success_email_sent", locale=language)
    return True, t("auth.register.success", locale=language)


def authenticate_user(email: str, password: str) -> tuple[bool, str, dict | None]:
    """Authenticate user. Returns (success, message, user_dict)."""
    email = email.strip().lower()
    password = password.strip()

    if not email or not password:
        return False, t("auth.login.required"), None

    init_db()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql(
                f"""
                SELECT password_hash, {_USER_SELECT_SQL}
                FROM users WHERE LOWER(email) = LOWER(?)
                """
            ),
            (email,),
        ).fetchone()

    if not row:
        return False, t("auth.login.unknown_email"), None
    if not _verify_password(password, row["password_hash"]):
        return False, t("auth.login.invalid"), None

    user = _row_to_user(row, include_created=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    from config import get_admin_emails

    should_promote = user["email"].strip().lower() in get_admin_emails()
    with _connect() as conn:
        if should_promote:
            conn.execute(
                adapt_sql("UPDATE users SET last_login_at = ?, is_admin = 1 WHERE id = ?"),
                (now, user["id"]),
            )
            user["is_admin"] = True
        else:
            conn.execute(
                adapt_sql("UPDATE users SET last_login_at = ? WHERE id = ?"),
                (now, user["id"]),
            )
    user["last_login_at"] = now
    return True, t("auth.login.success"), user


def update_user_profile(
    user_id: int,
    full_name: str,
    home_city: str,
    postal_code: str,
    admin_regions: list[str],
    selected_departments: list[dict[str, str]],
    selected_cities: list[str],
    all_cities: bool,
    country: str,
    contract_type: str,
    geo_filter_mode: str,
    search_radius_km: int,
    experience_level: str = "confirme",
    target_sectors: list[str] | None = None,
    target_job_title: str = "",
    job_max_age_days: int = 7,
    selected_countries: list[str] | None = None,
    geo_by_country: dict[str, dict[str, Any]] | None = None,
    phone: str | None = None,
) -> tuple[bool, str, dict | None]:
    """Update user profile and job-matching preferences."""
    full_name = " ".join(full_name.strip().split())
    phone_clean = " ".join(phone.strip().split()) if phone is not None else None
    home_city = " ".join(home_city.strip().split())
    regions = [r.strip() for r in (admin_regions or []) if r.strip()]
    departments = selected_departments or []
    admin_region, department_code, department_name = _legacy_geo_from_lists(
        regions, departments
    )
    cities = [c.strip() for c in (selected_cities or []) if c.strip()]
    if not all_cities and not cities and home_city:
        cities = [home_city]
    if all_cities:
        cities = []
    countries = [
        normalize_country_name(c)
        for c in (selected_countries or [country.strip() or "France"])
        if str(c).strip()
    ]
    geo_map = dict(geo_by_country or {})
    if "France" in countries:
        from world_geo import france_geo_from_profile

        geo_map["France"] = france_geo_from_profile(
            {
                "admin_regions": regions,
                "selected_departments": departments,
                "selected_cities": cities,
                "all_cities": all_cities,
            }
        )
    country = countries[0] if countries else "France"
    contract_type = normalize_contract_type(contract_type)
    geo_filter_mode = geo_filter_mode.strip().lower()
    experience_level = normalize_experience_level(experience_level)
    sectors = target_sectors or []
    job_title = " ".join(target_job_title.strip().split())
    publication_days = normalize_job_max_age_days(job_max_age_days)

    if len(full_name) < 2:
        return False, t("auth.name.min"), None

    valid_profile, profile_msg = _validate_profile_fields(
        home_city,
        postal_code,
        contract_type,
        geo_filter_mode,
        search_radius_km,
        experience_level,
        sectors,
        admin_regions=regions,
        selected_departments=departments,
        selected_cities=cities,
        all_cities=all_cities,
        target_job_title=job_title,
        selected_countries=countries,
        geo_by_country=geo_map,
    )
    if not valid_profile:
        return False, profile_msg, None

    init_db()
    with _connect() as conn:
        if phone_clean is not None:
            sql = """
                UPDATE users
                SET full_name = ?, home_city = ?, postal_code = ?, region = ?,
                    admin_region = ?, department_code = ?, department_name = ?,
                    contract_type = ?, search_radius_km = ?, geo_filter_mode = ?,
                    experience_level = ?, target_sectors = ?, country = ?,
                    admin_regions = ?, selected_departments = ?, selected_cities = ?,
                    all_cities = ?, selected_countries = ?, geo_by_country = ?,
                    target_job_title = ?, job_max_age_days = ?, phone = ?
                WHERE id = ?
                """
            params = (
                full_name,
                home_city,
                postal_code.strip(),
                admin_region,
                admin_region,
                department_code,
                department_name,
                contract_type,
                search_radius_km,
                geo_filter_mode,
                experience_level,
                serialize_target_sectors(sectors),
                country,
                serialize_admin_regions(regions),
                serialize_selected_departments(departments),
                serialize_selected_cities(cities),
                1 if all_cities else 0,
                serialize_selected_countries(countries),
                serialize_geo_by_country(geo_map),
                job_title,
                publication_days,
                phone_clean,
                user_id,
            )
        else:
            sql = """
                UPDATE users
                SET full_name = ?, home_city = ?, postal_code = ?, region = ?,
                    admin_region = ?, department_code = ?, department_name = ?,
                    contract_type = ?, search_radius_km = ?, geo_filter_mode = ?,
                    experience_level = ?, target_sectors = ?, country = ?,
                    admin_regions = ?, selected_departments = ?, selected_cities = ?,
                    all_cities = ?, selected_countries = ?, geo_by_country = ?,
                    target_job_title = ?, job_max_age_days = ?
                WHERE id = ?
                """
            params = (
                full_name,
                home_city,
                postal_code.strip(),
                admin_region,
                admin_region,
                department_code,
                department_name,
                contract_type,
                search_radius_km,
                geo_filter_mode,
                experience_level,
                serialize_target_sectors(sectors),
                country,
                serialize_admin_regions(regions),
                serialize_selected_departments(departments),
                serialize_selected_cities(cities),
                1 if all_cities else 0,
                serialize_selected_countries(countries),
                serialize_geo_by_country(geo_map),
                job_title,
                publication_days,
                user_id,
            )
        cursor = conn.execute(
            adapt_sql(sql),
            params,
        )
        if cursor.rowcount == 0:
            return False, t("auth.profile.not_found"), None

        row = conn.execute(
            adapt_sql(
                f"""
                SELECT {_USER_SELECT_SQL}
                FROM users WHERE id = ?
                """
            ),
            (user_id,),
        ).fetchone()

    return True, t("auth.profile.updated"), _row_to_user(row, include_created=True)


def change_password(
    user_id: int,
    current_password: str,
    new_password: str,
) -> tuple[bool, str]:
    """Change password for a logged-in user."""
    current_password = current_password.strip()
    new_password = new_password.strip()

    valid_pw, pw_msg = _validate_password(new_password)
    if not valid_pw:
        return False, pw_msg
    if current_password == new_password:
        return False, t("auth.password.same")

    init_db()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql("SELECT password_hash FROM users WHERE id = ?"),
            (user_id,),
        ).fetchone()

    if not row:
        return False, t("auth.profile.not_found")
    if not _verify_password(current_password, row["password_hash"]):
        return False, t("auth.password.current_wrong")

    with _connect() as conn:
        conn.execute(
            adapt_sql("UPDATE users SET password_hash = ? WHERE id = ?"),
            (_hash_password(new_password), user_id),
        )

    return True, t("auth.password.changed")


def reset_password(email: str, full_name: str, new_password: str) -> tuple[bool, str]:
    """
    Reset password after verifying e-mail and full name (no e-mail SMTP required).
    """
    email = email.strip().lower()
    full_name_norm = _normalize_name(full_name)
    new_password = new_password.strip()

    valid_pw, pw_msg = _validate_password(new_password)
    if not valid_pw:
        return False, pw_msg
    if not EMAIL_PATTERN.match(email):
        return False, t("auth.email.invalid")

    init_db()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql("SELECT id, full_name FROM users WHERE email = ?"),
            (email,),
        ).fetchone()

    if not row:
        return False, t("auth.reset.not_found")
    if _normalize_name(row["full_name"]) != full_name_norm:
        return False, t("auth.reset.name_mismatch")

    with _connect() as conn:
        conn.execute(
            adapt_sql("UPDATE users SET password_hash = ? WHERE id = ?"),
            (_hash_password(new_password), row["id"]),
        )

    return True, t("auth.reset.success")


def delete_user_account(user_id: int) -> tuple[bool, str]:
    """Permanently delete a user and every associated record.

    After success the same e-mail (and other profile details) can be used to
    create a new account and log in again.
    """
    init_db()
    from persistence import init_persistence_tables, release_user_identity

    init_persistence_tables()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql("SELECT id, email FROM users WHERE id = ?"),
            (user_id,),
        ).fetchone()
        if not row:
            return False, t("auth.profile.not_found")

        email = str(row["email"] or "")
        try:
            release_user_identity(conn, user_id, email)
            leftover = conn.execute(
                adapt_sql(
                    """
                    SELECT id FROM users
                    WHERE id = ? OR LOWER(email) = LOWER(?)
                    """
                ),
                (user_id, email or ""),
            ).fetchone()
        except Exception:  # noqa: BLE001 — never leave a half-deleted identity
            return False, t("auth.account.delete_failed")
        if leftover:
            return False, t("auth.account.delete_failed")

    return True, t("auth.account.deleted")


def update_user_preferred_language(user_id: int, locale: str) -> tuple[bool, str, dict | None]:
    """Update the user's UI language preference."""
    language = normalize_locale(locale)
    init_db()
    with _connect() as conn:
        conn.execute(
            adapt_sql("UPDATE users SET preferred_language = ? WHERE id = ?"),
            (language, user_id),
        )
        row = conn.execute(
            adapt_sql(
                f"""
                SELECT {_USER_SELECT_SQL}
                FROM users WHERE id = ?
                """
            ),
            (user_id,),
        ).fetchone()
    if not row:
        return False, t("auth.profile.not_found"), None
    return True, t("auth.profile.updated"), _row_to_user(row, include_created=True)


def format_member_since(iso_date: str) -> str:
    """Format registration date for display."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_date[:10]
