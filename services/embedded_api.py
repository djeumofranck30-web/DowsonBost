"""Run FastAPI next to Streamlit when no remote API_BASE_URL is set."""

from __future__ import annotations

import socket
import threading
import time
from typing import Any

from config import get_api_base_url, get_embedded_api_port, get_secret
from observability import get_logger

_lock = threading.Lock()
_started = False
_base_url = ""
_logger = get_logger(__name__)


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def _wait_health(url: str, *, timeout: float = 8.0) -> bool:
    from services.api_client import BackendClient

    deadline = time.time() + timeout
    client = BackendClient(url)
    while time.time() < deadline:
        if client.health():
            return True
        time.sleep(0.15)
    return False


def _start_uvicorn(host: str, port: int) -> None:
    import uvicorn

    from api.main import app

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def resolve_backend_url() -> str:
    """Remote URL if configured, otherwise the local embedded API."""
    remote = get_api_base_url()
    if remote:
        return remote
    port = get_embedded_api_port()
    return f"http://127.0.0.1:{port}"


def ensure_embedded_api() -> str:
    """Start FastAPI in a daemon thread for Streamlit Cloud / single-process hosts."""
    global _started, _base_url
    remote = get_api_base_url()
    if remote:
        _base_url = remote
        return remote

    port = get_embedded_api_port()
    host = get_secret("API_EMBEDDED_HOST", "127.0.0.1") or "127.0.0.1"
    url = f"http://{host}:{port}"
    with _lock:
        if _started:
            return _base_url or url
        if _port_open("127.0.0.1", port) and _wait_health(url, timeout=2.0):
            _started = True
            _base_url = url
            return url

        thread = threading.Thread(
            target=_start_uvicorn,
            args=(host, port),
            name="dowsonbost-api",
            daemon=True,
        )
        thread.start()
        if not _wait_health(url, timeout=10.0):
            raise RuntimeError(f"L'API FastAPI locale n'a pas démarré sur {url}")
        _started = True
        _base_url = url
        _logger.info("Embedded FastAPI listening on %s", url)
        return url


def backend_url() -> str:
    return _base_url or resolve_backend_url()


def using_remote_api() -> bool:
    return bool(get_api_base_url())


def backend_status() -> dict[str, Any]:
    return {
        "url": backend_url(),
        "remote": using_remote_api(),
        "embedded": _started and not using_remote_api(),
    }
