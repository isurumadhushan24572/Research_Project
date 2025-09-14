import streamlit as st
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime
import adlfs
import re

# --- Load env vars ---
load_dotenv()
SERVER = os.getenv("SYNAPSE_SERVER")
DATABASE = os.getenv("SYNAPSE_DB")
USERNAME = os.getenv("SYNAPSE_USER")
PASSWORD = os.getenv("SYNAPSE_PASS")
DRIVER = "ODBC Driver 17 for SQL Server"
AZURE_STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT")
AZURE_STORAGE_KEY = os.getenv("AZURE_STORAGE_KEY")
BRONZE_CONTAINER = os.getenv("BRONZE_CONTAINER")

# --- Synapse engine ---
engine = None
try:
    if SERVER and DATABASE and USERNAME and PASSWORD:
        conn_str = f"mssql+pyodbc://{USERNAME}:{PASSWORD}@{SERVER}:1433/{DATABASE}?driver={DRIVER}"
        engine = create_engine(conn_str)
    else:
        st.warning("⚠️ Missing environment variables! Check your .env file.")
except Exception as e:
    st.error(f"❌ Could not create DB engine: {e}")

# --- Streamlit page config ---
st.set_page_config(page_title="Teacher Portal", page_icon="📚", layout="centered")

# --- Session state ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "teacher_name" not in st.session_state:
    st.session_state.teacher_name = None
if "teacher_nic" not in st.session_state:
    st.session_state.teacher_nic = None

# --- Helper: get teacher info ---
def get_teacher(nic: str, birthdate: str):
    if engine is None:
        st.error("Database connection not available.")
        return None
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT TOP 1 Teacher_Name, NIC
                FROM gold.ext_teacher
                WHERE NIC = :nic AND Birth_Date = :birthdate
            """)
            result = conn.execute(query, {"nic": nic, "birthdate": birthdate}).fetchone()
            if result:
                return {"name": result.Teacher_Name, "nic": result.NIC}
            return None
    except Exception:
        return None

# --- Login form ---
if not st.session_state.logged_in:
    st.title("🔐 Teacher Login")
    with st.form("login_form"):
        nic = st.text_input("Enter NIC")
        birthdate = st.text_input("Enter Birthdate (YYYY-MM-DD)", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            teacher = get_teacher(nic, birthdate)
            if teacher:
                st.session_state.logged_in = True
                st.session_state.teacher_name = teacher["name"]
                st.session_state.teacher_nic = teacher["nic"]
                st.success(f"✅ Welcome {teacher['name']}! Redirecting...")
                st.rerun()
            else:
                st.error("❌ Invalid NIC or Birthdate")

# --- Submission form ---
else:
    st.title("📄 Teacher Form Submission")
    st.write(f"Welcome, **{st.session_state.teacher_name}** 👋")

    with st.form("submission_form"):
        subject = st.text_input("Main_Subject")
        other_subjects = st.text_input("Other_Subjects (comma-separated)")
        address = st.text_input("Address")
        notes = st.text_area("Reasons for transfer (comma-separated)")
        submitted = st.form_submit_button("Submit")

        if submitted:
            # Validate required fields
            if not subject or not address or not notes:
                st.error("❌ Please fill all required fields before submitting.")
            else:
                # Prepare Bronze path and filename
                now = datetime.now()
                yyyy_mm = now.strftime("%Y%m")  # YYYYMM
                nic_safe = re.sub(r'[^a-zA-Z0-9_-]', '_', st.session_state.teacher_nic)
                file_name = f"{nic_safe}_{yyyy_mm}.parquet"
                bronze_path = f"abfs://{BRONZE_CONTAINER}@{AZURE_STORAGE_ACCOUNT}.dfs.core.windows.net/Vaccancy_Details/"

                # Setup filesystem
                fs = adlfs.AzureBlobFileSystem(account_name=AZURE_STORAGE_ACCOUNT,
                                               account_key=AZURE_STORAGE_KEY)

                # Check if the file for this NIC and month already exists
                if fs.exists(f"{bronze_path}{file_name}"):
                    st.error("❌ You have already submitted the form for this month.")
                else:
                    # Create DataFrame
                
                    data = pd.DataFrame([{
                        "NIC": st.session_state.teacher_nic,
                        "Teacher_Name": st.session_state.teacher_name,
                        "Main_Subject": subject,
                        "Other_Subjects": other_subjects,
                        "Address": address,
                        "Notes": notes,
                        "Submitted_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])

                    # Write to Bronze
                    data.to_parquet(f"{bronze_path}{file_name}", index=False, filesystem=fs)

                    st.success("✅ Form submitted and saved Successfully!")
                    st.write(f"Subject: {subject}")
                    st.write(f"Other Subjects: {other_subjects}")
                    st.write(f"Address: {address}")
                    st.write(f"Notes: {notes}")
