import streamlit as st
from sqlalchemy import create_engine, text, bindparam
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime
import adlfs
import re
import requests

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
GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

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
for key in ["logged_in", "teacher_name", "teacher_nic", "teacher_title", "selected_subjects"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "logged_in" else False
if st.session_state.selected_subjects is None:
    st.session_state.selected_subjects = []

# --- Helper: get teacher info ---
def get_teacher(nic: str, birthdate: str):
    if engine is None:
        st.error("Database connection not available.")
        return None
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT TOP 1 Teacher_Name, NIC, Title
                FROM gold.ext_teacher
                WHERE NIC = :nic AND Birth_Date = :birthdate
            """)
            result = conn.execute(query, {"nic": nic, "birthdate": birthdate}).fetchone()
            if result:
                return {"name": result.Teacher_Name, "nic": result.NIC, "title": result.Title}
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

# --- Helper: get subject list (optimized) ---
def get_subjects(section: list):
    """
    Fetch distinct subjects for the selected section(s),
    ordered by SECTION then SUBJECT.
    """
    if engine is None or not section:
        return {}
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT DISTINCT SECTION, SUBJECT
                FROM gold.ext_subject
                WHERE SECTION IN :section
                ORDER BY SECTION, SUBJECT
            """).bindparams(
                bindparam("section", expanding=True)
            )
            result = conn.execute(query,{"section": section}).fetchall()

            subjects_by_section = {}
            for row in result:
                subjects_by_section.setdefault(row.SECTION, []).append(row.SUBJECT)

            return subjects_by_section
    except Exception as e:
        st.error(f"Error loading subject: {e}")
        return {}

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
                st.session_state.teacher_title = teacher["title"]
                st.success(f"✅ Welcome {teacher['title']} {teacher['name']}! Redirecting...")
                st.rerun()
            else:
                st.error("❌ Invalid NIC or Birthdate")

# --- Submission form ---
else:
    st.title("📄 Teacher Form Submission")
    st.write(f"Welcome, **{st.session_state.teacher_title} {st.session_state.teacher_name}** 👋")

    schools = get_schools()

    
    # --- Section logic ---
    
    section_options = ["Primary", "Secondary", "A/L_General", "A/L_Arts", "A/L_Commerce", "A/L_Technology", "A/L_Science"]
    section = st.multiselect("Select Section(s)", section_options)

    # --- Subjects (grouped by section with multiselects) ---
    subjects_by_section = get_subjects(section)
    # st.subheader("Select Subjects")
    selected_subjects = []

    for sec, subs in subjects_by_section.items():
        chosen = st.multiselect(
            f"{sec} Subjects",
            options=subs,
            default=[],
            key=f"subj_multi_{sec}"
        )
        selected_subjects.extend(chosen)

    st.session_state.selected_subjects = selected_subjects

    with st.form("submission_form"):
    # --- Other form fields ---
        address = st.text_input("Address")
        # notes_options = ["Health", "Hardship", "Family", "Personal"]
        Reason = st.text_area("Reasons for transfer")

        # --- School Preferences ---
        school_choices = []
        for i in range(5):
            choice = st.selectbox(
                f"School Preference {i+1}",
                ["-- None --"] + schools,
                key=f"school_pref_{i}"
            )
            if choice != "-- None --":
                school_choices.append(choice)

        # Form submit button
        submitted = st.form_submit_button("Submit")

        if submitted:
            if not st.session_state.selected_subjects or not address or not Reason.strip():
                st.error("❌ Please fill all required fields before submitting.")
            elif len(school_choices) == 0:
                st.error("❌ Please select at least one school.")
            elif len(school_choices) != len(set(school_choices)):
                st.error("❌ Duplicate schools selected. Each preference must be unique.")
            else:
                # ✅ Validate address using Google Maps API
                url = "https://maps.googleapis.com/maps/api/geocode/json"
                params = {"address": address, "key": GOOGLE_API_KEY}
                response = requests.get(url, params=params).json()

                if response["status"] != "OK":
                    st.error("❌ Invalid address. Please enter a valid location.")
                else:
                    validated_address = response["results"][0]["formatted_address"]

                    # ✅ Unique filename per NIC per month
                    current_month = datetime.now().strftime("%Y%m")
                    nic_safe = re.sub(r'[^a-zA-Z0-9_-]', '_', st.session_state.teacher_nic)
                    file_name = f"{nic_safe}_{current_month}.parquet"
                    bronze_path = f"abfs://{BRONZE_CONTAINER}@{AZURE_STORAGE_ACCOUNT}.dfs.core.windows.net/Vacancy_Details/"

                    fs = adlfs.AzureBlobFileSystem(
                        account_name=AZURE_STORAGE_ACCOUNT,
                        account_key=AZURE_STORAGE_KEY
                    )

                    if fs.exists(f"{bronze_path}{file_name}"):
                        st.error("❌ You have already submitted this month. Duplicate submissions are not allowed.")
                    else:
                        # ✅ Save to Parquet
                        data = pd.DataFrame([{
                            "NIC": st.session_state.teacher_nic,
                            "Teacher_Name": st.session_state.teacher_name,
                            "SECTION": ",".join(section),
                            "Subjects": ",".join(st.session_state.selected_subjects),
                            "Validated_Address": validated_address,
                            "School_Preferences": ",".join(school_choices),
                            "Reason": Reason,
                            "Submitted_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])

                        data.to_parquet(f"{bronze_path}{file_name}", index=False, filesystem=fs)

                        st.success("✅ Form submitted and saved successfully!")
                    
