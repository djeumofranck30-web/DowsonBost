"""User authentication for DowsonBost — SQLite (local) or PostgreSQL (production)."""

from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import bcrypt

from database import adapt_sql, connect, database_backend, existing_columns, is_unique_violation
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
    COUNTRY_OPTIONS,
    EXPERIENCE_LEVELS,
    GEO_FILTER_MODES,
    SECTOR_OPTIONS,
    normalize_contract_type,
    normalize_experience_level,
    parse_target_sectors,
    serialize_target_sectors,
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
    ("target_job_title", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
]


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
                target_job_title TEXT NOT NULL DEFAULT ''
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
            target_job_title TEXT NOT NULL DEFAULT ''
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


def init_db() -> None:
    """Create users table if it does not exist."""
    with _connect() as conn:
        _create_users_table(conn)
        _migrate_users(conn)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _validate_password(password: str) -> tuple[bool, str]:
    if len(password.strip()) < MIN_PASSWORD_LENGTH:
        return False, f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."
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
) -> tuple[bool, str]:
    title = " ".join(target_job_title.strip().split())
    if len(title) < 2:
        return False, "Indiquez l'intitulé du poste visé (au moins 2 caractères)."
    if home_city.strip() and len(home_city.strip()) < 2:
        return False, "La ville de domicile doit contenir au moins 2 caractères."
    postal = postal_code.strip()
    if postal and not POSTAL_CODE_PATTERN.match(postal):
        return False, "Code postal invalide (4 ou 5 chiffres)."

    regions = admin_regions or []
    if not regions and admin_region.strip():
        regions = [admin_region.strip()]
    if not regions:
        return False, "Sélectionnez au moins une région."

    departments = selected_departments or []
    if not departments and department_code.strip():
        departments = [{"code": department_code.strip().upper(), "name": "", "region": regions[0]}]
    if not departments:
        return False, "Sélectionnez au moins un département."

    cities = selected_cities or []
    if not all_cities:
        if not cities:
            cities = resolve_selected_cities({"home_city": home_city, "selected_cities": []})
        if not cities:
            return False, "Sélectionnez au moins une ville ou cochez « Toutes les villes »."
    normalized_contract = normalize_contract_type(contract_type)
    if normalized_contract not in CONTRACT_TYPES:
        return False, "Type de contrat invalide."
    if geo_filter_mode not in GEO_FILTER_MODES:
        return False, "Mode géographique invalide."
    if search_radius_km < 5 or search_radius_km > 200:
        return False, "Le rayon doit être entre 5 et 200 km."
    level = normalize_experience_level(experience_level)
    if level not in EXPERIENCE_LEVELS:
        return False, "Niveau d'expérience invalide."
    if target_sectors:
        invalid = [s for s in target_sectors if s not in SECTOR_OPTIONS]
        if invalid:
            return False, f"Secteur(s) invalide(s) : {', '.join(invalid)}."
    return True, ""


_USER_SELECT_SQL = """
    id, full_name, email, created_at, home_city, postal_code, region,
    admin_region, department_code, department_name,
    contract_type, search_radius_km, geo_filter_mode,
    experience_level, target_sectors, country,
    admin_regions, selected_departments, selected_cities, all_cities,
    target_job_title
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
    country = country.strip() or "France"
    contract_type = normalize_contract_type(contract_type)
    geo_filter_mode = geo_filter_mode.strip().lower()
    experience_level = normalize_experience_level(experience_level)
    sectors = target_sectors or []
    job_title = " ".join(target_job_title.strip().split())

    if len(full_name) < 2:
        return False, "Le nom doit contenir au moins 2 caractères."
    if not EMAIL_PATTERN.match(email):
        return False, "Adresse e-mail invalide."

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
                        target_job_title
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    job_title,
                ),
            )
    except Exception as exc:  # noqa: BLE001
        if is_unique_violation(exc):
            return False, "Un compte existe déjà avec cet e-mail."
        raise

    return True, "Compte créé avec succès. Vous pouvez vous connecter."


def authenticate_user(email: str, password: str) -> tuple[bool, str, dict | None]:
    """Authenticate user. Returns (success, message, user_dict)."""
    email = email.strip().lower()
    password = password.strip()

    if not email or not password:
        return False, "E-mail et mot de passe requis.", None

    init_db()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql(
                f"""
                SELECT password_hash, {_USER_SELECT_SQL}
                FROM users WHERE email = ?
                """
            ),
            (email,),
        ).fetchone()

    if not row:
        return False, "E-mail ou mot de passe incorrect.", None
    if not _verify_password(password, row["password_hash"]):
        return False, "E-mail ou mot de passe incorrect.", None

    return True, "Connexion réussie.", _row_to_user(row)


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
) -> tuple[bool, str, dict | None]:
    """Update user profile and job-matching preferences."""
    full_name = " ".join(full_name.strip().split())
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
    country = country.strip() or "France"
    contract_type = normalize_contract_type(contract_type)
    geo_filter_mode = geo_filter_mode.strip().lower()
    experience_level = normalize_experience_level(experience_level)
    sectors = target_sectors or []
    job_title = " ".join(target_job_title.strip().split())

    if len(full_name) < 2:
        return False, "Le nom doit contenir au moins 2 caractères.", None

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
    )
    if not valid_profile:
        return False, profile_msg, None

    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            adapt_sql(
                """
                UPDATE users
                SET full_name = ?, home_city = ?, postal_code = ?, region = ?,
                    admin_region = ?, department_code = ?, department_name = ?,
                    contract_type = ?, search_radius_km = ?, geo_filter_mode = ?,
                    experience_level = ?, target_sectors = ?, country = ?,
                    admin_regions = ?, selected_departments = ?, selected_cities = ?,
                    all_cities = ?, target_job_title = ?
                WHERE id = ?
                """
            ),
            (
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
                country.strip() or "France",
                serialize_admin_regions(regions),
                serialize_selected_departments(departments),
                serialize_selected_cities(cities),
                1 if all_cities else 0,
                job_title,
                user_id,
            ),
        )
        if cursor.rowcount == 0:
            return False, "Utilisateur introuvable.", None

        row = conn.execute(
            adapt_sql(
                f"""
                SELECT {_USER_SELECT_SQL}
                FROM users WHERE id = ?
                """
            ),
            (user_id,),
        ).fetchone()

    return True, "Profil mis à jour.", _row_to_user(row, include_created=True)


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
        return False, "Le nouveau mot de passe doit être différent de l'actuel."

    init_db()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql("SELECT password_hash FROM users WHERE id = ?"),
            (user_id,),
        ).fetchone()

    if not row:
        return False, "Utilisateur introuvable."
    if not _verify_password(current_password, row["password_hash"]):
        return False, "Mot de passe actuel incorrect."

    with _connect() as conn:
        conn.execute(
            adapt_sql("UPDATE users SET password_hash = ? WHERE id = ?"),
            (_hash_password(new_password), user_id),
        )

    return True, "Mot de passe modifié avec succès."


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
        return False, "Adresse e-mail invalide."

    init_db()
    with _connect() as conn:
        row = conn.execute(
            adapt_sql("SELECT id, full_name FROM users WHERE email = ?"),
            (email,),
        ).fetchone()

    if not row:
        return False, "Aucun compte trouvé avec cet e-mail."
    if _normalize_name(row["full_name"]) != full_name_norm:
        return False, "Le nom complet ne correspond pas à ce compte."

    with _connect() as conn:
        conn.execute(
            adapt_sql("UPDATE users SET password_hash = ? WHERE id = ?"),
            (_hash_password(new_password), row["id"]),
        )

    return True, "Mot de passe réinitialisé. Vous pouvez vous connecter."


def format_member_since(iso_date: str) -> str:
    """Format registration date for display."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_date[:10]
