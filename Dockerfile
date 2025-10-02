FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y \
    curl gnupg2 apt-transport-https \
    unixodbc unixodbc-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 17 for SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 && \
    rm -rf /var/lib/apt/lists/*

# App
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Streamlit runtime config
ENV PORT=8000
# which file to run (override per Web App)
ENV ENTRY_FILE=app.py

EXPOSE 8000
CMD ["sh", "-c", "python -m streamlit run ${ENTRY_FILE} --server.address 0.0.0.0 --server.port ${PORT}"]
