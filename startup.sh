#!/usr/bin/env bash
set -e

# Move to code folder
cd /home/site/wwwroot

# Clean old Microsoft repos (prevents debian/12 conflicts)
rm -f /etc/apt/sources.list.d/mssql-release.list

# Install MS ODBC Driver 17
apt-get update
apt-get install -y curl gnupg2 apt-transport-https unixodbc unixodbc-dev
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Python deps (oryx installs, but ensure if not using build)
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# Run Streamlit (default to app.py; override in Startup Command if needed)
python -m streamlit run ${ENTRY_FILE:-app.py} --server.address 0.0.0.0 --server.port 8000
