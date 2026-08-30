#!/usr/bin/env python3
"""Dedicated analysis worker — use on Fly / OVH when you want extra machines.

The web process already runs an in-process worker. This script is optional:
  ANALYSIS_WORKER_EMBEDDED=0 streamlit run app.py
  python scripts/run_analysis_worker.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_secrets_from_toml() -> None:
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.is_file():
        return
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    with secrets_path.open("rb") as handle:
        data = tomllib.load(handle)
    for key, value in data.items():
        if isinstance(value, str) and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    _load_secrets_from_toml()
    from auth import init_db
    from database import configure_database
    from observability import get_logger, setup_logging
    from services.analysis_worker import run_analysis_worker_forever

    setup_logging()
    logger = get_logger(__name__)
    configure_database(
        os.environ.get("DATABASE_URL", ""),
        password=os.environ.get("DATABASE_PASSWORD", ""),
    )
    init_db()
    logger.info("Analysis worker started — waiting for tickets")
    print("Analysis worker started. Ctrl+C to stop.", flush=True)
    run_analysis_worker_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
