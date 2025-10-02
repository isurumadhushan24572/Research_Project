#!/usr/bin/env bash
set -e

cd /home/site/wwwroot

# 🔹 Remove any Debian 12 (bookworm) repo Azure might pre-add
rm -f /etc/apt/sources.list.d/*debian*12*.list || true

# 🔹 Install MS ODBC Driver 17 (Debian 11 only)
apt-get update || true
DEBIAN_FRONTEND=noninteractive apt-get install -y curl gnupg2 apt-transport-https unixodbc unixodbc-dev || true
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update || true
ACCEPT_EULA=Y DEBIAN_FRONTEND=noninteractive apt-get install -y msodbcsql17 || true

# 🔹 Python deps
if [ -f requirements.txt ]; then pip install -r requirements.txt || true; fi

# 🔹 Run Streamlit
echo "🚀 Starting Streamlit app..."
python -m streamlit run ${ENTRY_FILE:-app.py} --server.address 0.0.0.0 --server.port 8000
