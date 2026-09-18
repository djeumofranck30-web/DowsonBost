#!/bin/sh
# Bind Streamlit to the platform PORT (Fly / Docker / OVH).
# Do not start FastAPI next to Streamlit: a localhost HTTP hop slows every click.
set -eu
PORT="${PORT:-8501}"
exec streamlit run app.py \
  --server.port="$PORT" \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false \
  --client.showSidebarNavigation=false
