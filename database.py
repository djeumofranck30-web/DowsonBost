"""Database connection layer — SQLite (local) or PostgreSQL (production)."""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse, urlunparse

SQLITE_PATH = Path(__file__).parent / "data" / "users.db"

_backend: str = "sqlite"
_database_url: str = ""
_database_password: str = ""
_configured = False
_pg_local = threading.local()
_sqlite_local = threading.local()


class DatabaseConfigError(ValueError):
    """Invalid DATABASE_URL configuration."""


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].strip()
    return value


def _clean_password(value: str) -> str:
    """Strip quotes and accidental bracket wrapping from passwords."""
    password = _strip_quotes(value)
    if len(password) >= 2 and password[0] == "[" and password[-1] == "]":
        password = password[1:-1]
    return password


def _merge_password_into_url(url: str, password: str) -> str:
    """Inject or replace password in a PostgreSQL URL."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        raise DatabaseConfigError("DATABASE_URL invalide — format attendu : postgresql://user:pass@host:port/db")

    username = parsed.username or "postgres"
    encoded_password = quote(password, safe="")
    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:{encoded_password}@{host}{port}"
    return urlunparse(parsed._replace(netloc=netloc))


def normalize_database_url(url: str, password_override: str = "") -> str:
    """Normalize and validate a PostgreSQL connection URL."""
    url = _strip_quotes(url)
    password_override = _clean_password(password_override)

    if not url:
        return ""

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    if not url.startswith("postgresql://"):
        raise DatabaseConfigError(
            "DATABASE_URL doit commencer par postgresql:// (copiez l'URL depuis Supabase → Connect)."
        )

    if "[YOUR-PASSWORD]" in url or "YOUR-PASSWORD" in url:
        url = url.replace("[YOUR-PASSWORD]", "")
        if ":@" in url:
            url = url.replace(":@", "@")

    parsed = urlparse(url)
    if parsed.password and ("@" in unquote(parsed.password) or "[" in parsed.password):
        raise DatabaseConfigError(
            "Le mot de passe dans DATABASE_URL contient @ ou des crochets — "
            "retirez-le de l'URL et utilisez DATABASE_PASSWORD à la place."
        )

    if password_override:
        url = _merge_password_into_url(url, password_override)
    elif not urlparse(url).password:
        # URL without password — DATABASE_PASSWORD will be merged at connect time.
        pass

    parsed = urlparse(url)
    if not parsed.hostname:
        raise DatabaseConfigError("DATABASE_URL invalide — hôte manquant.")

    if not parsed.path or parsed.path == "/":
        url = urlunparse(parsed._replace(path="/postgres"))

    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    host = (parsed.hostname or "").lower()

    if "supabase" in host or "neon" in host:
        if "sslmode" not in query:
            query["sslmode"] = ["require"]

    new_query = urlencode([(k, v[0]) for k, v in query.items() if k in {"sslmode"}])
    return urlunparse(parsed._replace(query=new_query))


def configure_database(url: str = "", password: str = "") -> str:
    """Select SQLite (default) or PostgreSQL when DATABASE_URL is set."""
    global _backend, _database_url, _database_password, _configured
    raw_url = (url or os.getenv("DATABASE_URL", "")).strip()
    raw_password = _clean_password(password or os.getenv("DATABASE_PASSWORD", ""))

    if raw_url.startswith(("postgres://", "postgresql://")):
        _database_url = normalize_database_url(raw_url, raw_password)
        _database_password = raw_password
        if not urlparse(_database_url).password and not _database_password:
            raise DatabaseConfigError(
                "Mot de passe PostgreSQL manquant. Ajoutez DATABASE_PASSWORD dans les secrets Streamlit."
            )
        if _database_password and not urlparse(_database_url).password:
            _database_url = _merge_password_into_url(_database_url, _database_password)
        _backend = "postgres"
        _close_sqlite_connection()
    else:
        _database_url = ""
        _database_password = ""
        _backend = "sqlite"
        _close_postgres_connection()
    _configured = True
    return _backend


def _close_postgres_connection() -> None:
    conn = getattr(_pg_local, "conn", None)
    if conn is None:
        return
    with suppress(Exception):
        conn.close()
    _pg_local.conn = None


def _close_sqlite_connection() -> None:
    conn = getattr(_sqlite_local, "conn", None)
    if conn is None:
        return
    with suppress(Exception):
        conn.close()
    _sqlite_local.conn = None
    _sqlite_local.path = None


def ensure_configured() -> None:
    if not _configured:
        configure_database(os.getenv("DATABASE_URL", ""), os.getenv("DATABASE_PASSWORD", ""))


def database_backend() -> str:
    ensure_configured()
    return _backend


def database_status() -> tuple[str, str]:
    """Return (backend_label, message) for diagnostics."""
    ensure_configured()
    if _backend == "postgres":
        host = "PostgreSQL distant"
        try:
            parsed = urlparse(_database_url)
            if parsed.hostname:
                host = parsed.hostname
        except Exception:  # noqa: BLE001
            pass
        return "postgres", f"Base persistante PostgreSQL ({host}) — comptes conservés après déploiement."
    return "sqlite", (
        "SQLite local (data/users.db) — les comptes sont effacés à chaque redéploiement "
        "Streamlit Cloud. Ajoutez DATABASE_URL (Supabase/Neon) dans les secrets."
    )


def database_connection_hint(exc: BaseException) -> str:
    """User-facing hint from a PostgreSQL connection failure."""
    message = str(exc).lower()
    hints = [
        "Vérifiez DATABASE_URL dans Streamlit Cloud → Settings → Secrets, puis Reboot app.",
    ]
    if "password" in message or "authentication" in message:
        hints.append(
            "Mot de passe incorrect : réinitialisez-le dans Supabase (Settings → Database), "
            "puis mettez-le dans DATABASE_URL ou DATABASE_PASSWORD."
        )
        hints.append(
            "Si le mot de passe contient @ # ! % etc., utilisez DATABASE_PASSWORD séparément "
            "(sans l'encoder) ou encodez-le dans l'URL."
        )
    if "ssl" in message or "certificate" in message:
        hints.append("L'URL doit inclure sslmode=require (ajouté automatiquement pour Supabase).")
    if "timeout" in message or "could not translate host" in message or "name or service not known" in message:
        hints.append(
            "Utilisez l'URL du pooler Supabase (Connect → Session pooler ou Transaction pooler), "
            "pas la connexion directe db.xxx.supabase.co si elle échoue."
        )
    if "placeholder" in message or "your-password" in message:
        hints.append("Remplacez [YOUR-PASSWORD] par le vrai mot de passe Supabase.")
    if "prepared statement" in message:
        hints.append(
            "Le pooler transactionnel Supabase (port 6543) refuse les requêtes préparées. "
            "Reboot l'app Streamlit Cloud pour charger la version qui les désactive."
        )
    if "ipv4" in message or "ipv6" in message:
        hints.append(
            "URL mal formée : mettez DATABASE_URL entre guillemets et utilisez DATABASE_PASSWORD "
            "si le mot de passe contient @ ou d'autres caractères spéciaux."
        )
        hints.append(
            "Exemple : DATABASE_URL sans mot de passe dans l'URL + DATABASE_PASSWORD séparé."
        )
    return "\n".join(f"- {hint}" for hint in hints)


_PG_CONNECTION_ERROR_MARKERS = (
    "connection refused",
    "could not connect",
    "server closed the connection",
    "ssl connection has been closed",
    "connection already closed",
    "connection not open",
    "timeout expired",
    "could not translate host",
    "name or service not known",
    "no route to host",
    "network is unreachable",
    "connection reset",
    "eof detected",
)


def uses_transaction_pooler(url: str = "") -> bool:
    """True for Supabase/Neon PgBouncer transaction poolers (port 6543)."""
    parsed = urlparse(url or _database_url)
    host = (parsed.hostname or "").lower()
    port = int(parsed.port or 5432)
    return port == 6543 or "pooler" in host


def is_postgres_connection_error(exc: BaseException) -> bool:
    """Transport/auth failures only — not SQL errors or missing tables."""
    if isinstance(exc, DatabaseConfigError):
        return False
    try:
        from psycopg import InterfaceError, OperationalError
    except ImportError:
        InterfaceError = ()  # type: ignore[assignment,misc]
        OperationalError = ()  # type: ignore[assignment,misc]
    if isinstance(exc, (OperationalError, InterfaceError)):
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _PG_CONNECTION_ERROR_MARKERS)


def postgres_client_connect_kwargs() -> dict[str, Any]:
    """psycopg client options. Prepared statements break PgBouncer transaction mode.

    ``prepare_threshold=0`` means “prepare on the first query”. Use ``None`` to
    disable named statements entirely (required for Supabase port 6543).
    """
    return {"autocommit": False, "prepare_threshold": None}


def postgres_connect_kwargs(url: str) -> dict[str, Any]:
    """Build psycopg connection parameters."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    host = parsed.hostname
    if not host:
        raise DatabaseConfigError("Hôte PostgreSQL manquant dans DATABASE_URL.")

    password = unquote(parsed.password or "")
    if not password:
        raise DatabaseConfigError(
            "Mot de passe PostgreSQL manquant. Ajoutez DATABASE_PASSWORD dans les secrets Streamlit."
        )

    sslmode = (query.get("sslmode") or ["require"])[0]
    return {
        "host": host,
        "port": parsed.port or 5432,
        "user": unquote(parsed.username or "postgres"),
        "password": password,
        "dbname": (parsed.path or "/postgres").lstrip("/") or "postgres",
        "sslmode": sslmode,
        "connect_timeout": 20,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }


def postgres_conninfo(url: str) -> str:
    """Build a libpq conninfo string with proper escaping (handles @ in passwords)."""
    import psycopg

    params = postgres_connect_kwargs(url)
    return psycopg.conninfo.make_conninfo(**params)


def postgres_connection_summary(url: str) -> str:
    """Safe one-line summary for error messages (no password)."""
    try:
        params = postgres_connect_kwargs(url)
        return (
            f"hôte={params['host']} port={params['port']} "
            f"user={params['user']} db={params['dbname']}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"URL illisible ({exc})"


def adapt_sql(sql: str) -> str:
    """Convert placeholders for the active backend."""
    if database_backend() == "postgres":
        return sql.replace("?", "%s")
    return sql


def is_unique_violation(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    try:
        from psycopg.errors import UniqueViolation

        return isinstance(exc, UniqueViolation)
    except ImportError:
        return False


def existing_columns(conn: Any, table: str = "users") -> set[str]:
    if database_backend() == "postgres":
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        ).fetchall()
        return {row["column_name"] for row in rows}

    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _is_prepared_statement_conflict(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "prepared statement" in message and (
        "already exists" in message or "does not exist" in message
    )


def _disable_prepared_statements(conn: Any) -> None:
    """Force-disable psycopg named statements even if connect() ignored the kwarg."""
    with suppress(Exception):
        conn.prepare_threshold = None


def _reset_pooler_backend(conn: Any) -> None:
    """Drop leftover prepared statements on a recycled PgBouncer backend."""
    if not uses_transaction_pooler(_database_url):
        return
    conn.execute("DEALLOCATE ALL")


def _acquire_postgres_connection(row_factory: Any) -> Any:
    """Open a Postgres connection, retrying once on a dead or dirty pooler socket."""
    import psycopg

    reuse = not uses_transaction_pooler(_database_url)
    existing = getattr(_pg_local, "conn", None)
    if reuse and existing is not None and not getattr(existing, "closed", True):
        return existing
    if existing is not None:
        _close_postgres_connection()

    conninfo = postgres_conninfo(_database_url)
    client_kwargs = postgres_client_connect_kwargs()
    last_exc: BaseException | None = None
    for _attempt in range(2):
        try:
            try:
                conn = psycopg.connect(conninfo, row_factory=row_factory, **client_kwargs)
            except TypeError:
                conn = psycopg.connect(conninfo, row_factory=row_factory)
            _disable_prepared_statements(conn)
            _reset_pooler_backend(conn)
            _pg_local.conn = conn
            return conn
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            _close_postgres_connection()
            if not (
                is_postgres_connection_error(exc) or _is_prepared_statement_conflict(exc)
            ):
                raise
    assert last_exc is not None
    raise last_exc


def _postgres_connection_failure(exc: BaseException) -> RuntimeError:
    summary = postgres_connection_summary(_database_url)
    return RuntimeError(
        f"Connexion PostgreSQL impossible ({summary}).\n" + database_connection_hint(exc)
    )


@contextmanager
def connect() -> Iterator[Any]:
    """Yield a DB connection for the configured backend."""
    ensure_configured()
    if database_backend() == "postgres":
        from psycopg.rows import dict_row

        conn = None
        try:
            conn = _acquire_postgres_connection(dict_row)
            try:
                yield conn
                conn.commit()
            except Exception:
                with suppress(Exception):
                    conn.rollback()
                raise
        except DatabaseConfigError:
            _close_postgres_connection()
            raise
        except Exception as exc:  # noqa: BLE001
            _close_postgres_connection()
            if is_postgres_connection_error(exc):
                raise _postgres_connection_failure(exc) from exc
            raise
        finally:
            if uses_transaction_pooler(_database_url):
                _close_postgres_connection()
    else:
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        path = str(SQLITE_PATH)
        conn = getattr(_sqlite_local, "conn", None)
        if conn is None or getattr(_sqlite_local, "path", None) != path:
            if conn is not None:
                with suppress(Exception):
                    conn.close()
            conn = sqlite3.connect(path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            _sqlite_local.conn = conn
            _sqlite_local.path = path
        try:
            yield conn
            conn.commit()
        except Exception:
            with suppress(Exception):
                conn.rollback()
            raise
