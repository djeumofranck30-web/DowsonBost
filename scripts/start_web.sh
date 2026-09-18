#!/bin/sh
# Bind Streamlit to the platform PORT (Fly / Docker / OVH).
# FastAPI owns the database; Streamlit is display-only.
set -eu
PORT="${PORT:-8501}"
API_PORT="${API_EMBEDDED_PORT:-8765}"

if [ -z "${API_BASE_URL:-}" ]; then
  python scripts/run_api.py &
  export API_BASE_URL="http://127.0.0.1:8000"
  export API_EMBEDDED_PORT="$API_PORT"
  i=0
  while [ "$i" -lt 50 ]; do
    if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" >/dev/null 2>&1; then
      break
    fi
    i=$((i + 1))
    sleep 0.2
  done
fi

exec streamlit run app.py \
  --server.port="$PORT" \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false \
  --client.showSidebarNavigation=false
