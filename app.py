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

# --- Helper: get school list ---
def get_schools():
    if engine is None:
        return []
    try:
        with engine.connect() as conn:
            query = text("SELECT DISTINCT School_Name FROM gold.ext_school")
            result = conn.execute(query).fetchall()
            return [row.School_Name for row in result]
    except Exception as e:
        st.error(f"Error loading schools: {e}")
        return []

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

    schools = get_schools()

    with st.form("submission_form"):
        subject = st.text_input("Subject (comma-separated)")
        address = st.text_input("Address")
        # notes = st.text_area("Reasons for transfer (comma-separated)")
        notes_options = ["Health","Hardship","Family", "Personal"]
        Reason = st.multiselect("Reasons for transfer", notes_options)

        # --- School Preferences ---
        school_choices = []
        for i in range(5):  # max 5 preferences
            choice = st.selectbox(
                f"School Preference {i+1}",
                ["-- None --"] + schools,
                key=f"school_pref_{i}"
            )
            if choice != "-- None --":
                school_choices.append(choice)

        submitted = st.form_submit_button("Submit")

        if submitted:
            # Validate required fields
            if not subject or not address :
                st.error("❌ Please fill all required fields before submitting.")
            elif len(school_choices) == 0:
                st.error("❌ Please select at least one school.")
            elif len(school_choices) != len(set(school_choices)):
                st.error("❌ Duplicate schools selected. Each preference must be unique.")
            else:
                # Prepare data
                current_month = datetime.now().strftime("%Y%m")
                nic_safe = re.sub(r'[^a-zA-Z0-9_-]', '_', st.session_state.teacher_nic)
                file_name = f"{nic_safe}_{current_month}.parquet"
                bronze_path = f"abfs://{BRONZE_CONTAINER}@{AZURE_STORAGE_ACCOUNT}.dfs.core.windows.net/Vacancy_Details/"

                fs = adlfs.AzureBlobFileSystem(account_name=AZURE_STORAGE_ACCOUNT,
                                               account_key=AZURE_STORAGE_KEY)

                # Check if already exists
                if fs.exists(f"{bronze_path}{file_name}"):
                    st.error("❌ You have already submitted this month. Duplicate submissions are not allowed.")
                else:
                    data = pd.DataFrame([{
                        "NIC": st.session_state.teacher_nic,
                        "Teacher_Name": st.session_state.teacher_name,
                        "Subjects": subject,
                        "Address": address,
                        "School_Preferences": ",".join(school_choices),
                        "Reason": ",".join(Reason),
                        "Submitted_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])

                    # Save to Bronze
                    data.to_parquet(f"{bronze_path}{file_name}", index=False, filesystem=fs)

                    st.success("✅ Form submitted and saved successfully!")
                    st.write(f"**Saved as:** {file_name}")
