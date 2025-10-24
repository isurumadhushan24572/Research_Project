Teacher Transfer Management System

This repository contains a Streamlit-based Teacher Transfer Management System with two primary applications:

- `app.py` — Teacher Portal (teacher login and transfer submission)  
  ![Teacher Portal](QR/Teacher_20251017_184333.png)
- `admin.py` — Admin Dashboard (admin login, KPIs, matching, exports)  
  ![Admin Dashboard](QR/Admin_20251017_184244.png)

## Overview

The system allows teachers to securely submit transfer requests and administrators to review, match, and export transfer data. Key features are:

- Teacher login (NIC + birthdate) and form submission with Google Maps address validation.
- Submission storage as Parquet files in Azure Data Lake (bronze stage).
- Admin dashboard with KPIs, division-wise counts, vacancy details, and matching views (reciprocal and top-10).
- Export capability to Excel for filtered vacancy or match results.

## Files of interest

- `app.py` (Teacher Portal)
	- Streamlit app for teachers to login and submit transfer requests.
	- Uses SQLAlchemy for Synapse connectivity to validate teachers and to load lookup lists.
	- Validates addresses via Google Maps Geocoding API before saving.
	- Saves submissions to Azure Data Lake as Parquet files using `adlfs`.

- `admin.py` (Admin Dashboard)
	- Streamlit app for administrators to login and view KPIs and detailed data.
	- Connects to Synapse via `pyodbc` and runs queries to compute KPIs and load tables.
	- Provides filtering, formatting, and Excel export for vacancy and match datasets.

## Documentation

- Teacher Portal Guide (updated): [Portal_Guideline/Teacher_Portal_Guide.md](Portal_Guideline/Teacher_Portal_Guide.md)
	- Covers login with NIC/Birth/Appointment Date, OTP verification (5‑minute expiry, resend), address validation rules for Sri Lanka, selecting sections/subjects, school preferences (up to 5 unique), monthly submission limit, and troubleshooting.

## Setup

1. Create a Python virtual environment and activate it (Windows PowerShell):

```powershell
python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Create a `.env` file in the repository root and set the following environment variables:

```text
SYNAPSE_SERVER=your_synapse_server
SYNAPSE_DB=your_database
SYNAPSE_USER=your_username
SYNAPSE_PASS=your_password
AZURE_STORAGE_ACCOUNT=your_storage_account
AZURE_STORAGE_KEY=your_storage_key
BRONZE_CONTAINER=your_bronze_container
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

Notes:
- The app expects an ODBC driver for SQL Server (e.g. "ODBC Driver 17 for SQL Server") to be installed for `pyodbc`.
- For `app.py`, the code builds a SQLAlchemy engine using the `mssql+pyodbc` dialect; ensure the `USERNAME`, `PASSWORD`, `SERVER`, and `DATABASE` environment variables are correct.

## Run

- Run the Teacher Portal:

```powershell
streamlit run app.py
```

- Run the Admin Dashboard:

```powershell
streamlit run admin.py
```

## Security & Deployment Notes

- Keep `.env` out of source control. Use a secure secret manager for production.
- Validate table names when building dynamic queries to avoid SQL injection. `admin.py` uses `pd.read_sql(f"SELECT * FROM {table_name}", conn)` which should only be fed trusted table names or validated against an allowlist.
- Limit database accounts to least-privilege access.

## Suggestions / Next Steps

- Add unit tests for helper functions (DB connection, data formatting).
- Add integration test that runs Streamlit page components with mocked DB responses.
- Add CI workflow to run linting and tests on push.
- Add a short CHANGELOG and CONTRIBUTING guide.


