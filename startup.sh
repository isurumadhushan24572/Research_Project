#!/usr/bin/env bash
set -e

cd /home/site/wwwroot

# Just install Python deps
if [ -f requirements.txt ]; then pip install -r requirements.txt || true; fi

# Run Streamlit
echo "🚀 Starting Streamlit (test mode, no ODBC)..."
python -m streamlit run ${ENTRY_FILE:-app.py} --server.address 0.0.0.0 --server.port 8000
