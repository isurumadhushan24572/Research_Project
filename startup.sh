#!/usr/bin/env bash
set -e

cd /home/site/wwwroot

# Clean any old Microsoft repos (Debian 12 references)
rm -f /etc/apt/sources.list.d/*debian*12*.list || true
rm -f /etc/apt/sources.list.d/mssql-release.list || true

# Install MS ODBC Driver 17 (Debian 11 only)
apt-get update || true
apt-get install -y curl gnupg2 apt-transport-https unixodbc unixodbc-dev
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update || true
ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Python deps
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# Run Streamlit
python -m streamlit run ${ENTRY_FILE:-app.py} --server.address 0.0.0.0 --server.port 8000
#streamlit run ${ENTRY_FILE:-app.py} --server.address