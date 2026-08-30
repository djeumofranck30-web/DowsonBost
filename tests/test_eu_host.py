"""EU host stays in Paris next to a Paris Supabase project."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fly_pins_paris_eu_and_stays_awake():
    fly = (ROOT / "fly.toml").read_text(encoding="utf-8")
    assert 'primary_region = "cdg"' in fly
    assert "lhr" not in fly
    assert "eu-west-2" not in fly
    assert "eu-west-3" in fly
    assert 'auto_stop_machines = "off"' in fly
    assert "min_machines_running = 1" in fly
    assert 'DATABASE_POOL_MODE = "session"' in fly
    assert "/_stcore/health" in fly


def test_container_starts_streamlit_on_all_interfaces():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    start = (ROOT / "scripts/start_web.sh").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "DATABASE_POOL_MODE=session" in dockerfile
    assert "scripts/start_web.sh" in dockerfile
    assert "--server.address=0.0.0.0" in start
    assert "DATABASE_POOL_MODE: session" in compose
