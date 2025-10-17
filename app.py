import streamlit as st
from sqlalchemy import create_engine, text, bindparam
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime, timedelta
import adlfs
import re
import requests
import difflib
import base64
from pathlib import Path

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
# Text.LK credentials
TEXTLK_API_KEY = os.getenv("TEXTLK_API_KEY")  # Text.LK API key
TEXTLK_SENDER_ID = os.getenv("TEXTLK_SENDER_ID")  # Text.LK sender ID
TEXTLK_ENDPOINT = os.getenv("TEXTLK_ENDPOINT", "https://app.text.lk/api/v3/sms/send")
OTP_DEBUG = os.getenv("OTP_DEBUG", "false").lower() in {"1","true","yes","on"}

# --- Synapse engine ---
engine = None
try:
    if SERVER and DATABASE and USERNAME and PASSWORD:
        conn_str = f"mssql+pyodbc://{USERNAME}:{PASSWORD}@{SERVER}:1433/{DATABASE}?driver={DRIVER}"
        engine = create_engine(conn_str)
    else:
        st.warning("⚠️ Missing environment variables! Check your .env file.")
except Exception as e:  # noqa: BLE001
    st.error(f"❌ Could not create DB engine: {e}")

# --- Session state init ---
for key, default in {
    "logged_in": False,
    "teacher_name": None,
    "teacher_nic": None,
    "teacher_title": None,
    "selected_subjects": [],
    "otp_sent": False,
    "otp_code": None,
    "otp_expiry": None,
    "mobile_number": None,
    "login_stage": "credentials",  # credentials -> otp
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --- Helper: send OTP via Text.lk (server-generated) ---
def normalize_sri_lanka_mobile(raw: str) -> str | None:
    """Normalize Sri Lankan mobile numbers into E.164 +94 format.

    Accepted input examples:
        0712345678
        712345678
        +94712345678
        0094712345678
        94 71 234 5678
    Rules:
        - Must be a mobile prefix (070,071,072,074,075,076,077,078)
        - Total national significant number length must be 9 (7X########)
    Returns normalized +94XXXXXXXXX or None if invalid.
    """
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9+]", "", raw.strip())
    # Remove leading 00 for international
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if cleaned.startswith("+"):
        if not cleaned.startswith("+94"):
            return None
        digits = cleaned[3:]
    elif cleaned.startswith("94"):
        digits = cleaned[2:]
    elif cleaned.startswith("0"):
        digits = cleaned[1:]
    else:
        # Assume already national without leading zero (e.g., 712345678)
        digits = cleaned
    # Now digits should be 9 numbers
    if not digits.isdigit() or len(digits) != 9:
        return None
    if digits[:2] not in {"70","71","72","74","75","76","77","78"}:
        return None
    return "+94" + digits
def send_textlk_otp(mobile: str, length: int = 6) -> tuple[bool, str]:
    """Send an OTP via Text.lk using type='otp' and {{OTPx}} shortcode.

    Returns (True, otp) on success, else (False, error_message).
    """
    if not (TEXTLK_API_KEY and TEXTLK_SENDER_ID):
        return False, "Missing TEXTLK credentials."
    # Text.lk expects recipient without '+' e.g., 9471xxxxxxx
    recipient = mobile.replace("+", "")
    otp_len = max(4, min(int(length or 6), 8))  # clamp to [4,8]
    # Note: To produce '{{OTP6}}' in a Python f-string, you must escape braces: '{{{{OTP6}}}}'
    message = f"Your Teacher Portal verification code is: {{{{OTP{otp_len}}}}}"
    payload = {
        "recipient": recipient,
        "sender_id": TEXTLK_SENDER_ID,
        "type": "otp",
        "message": message,
    }
    headers = {
        "Authorization": f"Bearer {TEXTLK_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        resp = requests.post(TEXTLK_ENDPOINT, json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        if (data.get("status") == "success") and isinstance(data.get("data"), dict):
            otp_value = data["data"].get("otp")
            if otp_value is None:
                return False, "No OTP in response."
            return True, str(otp_value)
        return False, f"Unexpected response: {data}"
    except requests.exceptions.Timeout:
        return False, "Request timeout."
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {e}"
    except Exception as e:  # noqa: BLE001
        return False, f"Exception: {e}"

# --- Helper: get teacher including Appointment Date & Mobile ---
def get_teacher_with_meta(nic: str, birthdate: str, appointment_day: str):
    if engine is None:
        st.error("Database connection not available.")
        return None
    try:
        with engine.connect() as conn:
            query = text(
                """
                SELECT TOP 1 Teacher_Name, NIC, Title, Appointment_Day, Mobile_Number
                FROM gold.ext_teacher
                WHERE NIC = :nic 
                  AND Birth_Date = :birthdate 
                  AND Appointment_Day = :appointment_day
                  AND Type = 'Provintial'
                """
            )
            result = conn.execute(query, {
                "nic": nic,
                "birthdate": birthdate,
                "appointment_day": appointment_day,
            }).fetchone()
            if result:
                return {
                    "name": result.Teacher_Name,
                    "nic": result.NIC,
                    "title": result.Title,
                    "appointment_day": str(result.Appointment_Day),
                    "mobile": str(result.Mobile_Number) if result.Mobile_Number else None,
                }
            return None
    except Exception:
        return None

# --- Subject / School helpers (copied & trimmed from main app) ---
def get_schools():
    if engine is None:
        return []
    try:
        with engine.connect() as conn:
            query = text("SELECT DISTINCT School_Name FROM gold.ext_school WHERE Type = 'Provintial'")
            result = conn.execute(query).fetchall()
            return [row.School_Name for row in result]
    except Exception as e:  # noqa: BLE001
        st.error(f"Error loading schools: {e}")
        return []

def get_subjects(section: list):
    if engine is None or not section:
        return {}
    try:
        with engine.connect() as conn:
            query = text(
                """
                SELECT DISTINCT SECTION, SUBJECT
                FROM gold.ext_subject
                WHERE SECTION IN :section
                ORDER BY SECTION, SUBJECT
                """
            ).bindparams(bindparam("section", expanding=True))
            result = conn.execute(query, {"section": section}).fetchall()
            subjects_by_section = {}
            for row in result:
                subjects_by_section.setdefault(row.SECTION, []).append(row.SUBJECT)
            return subjects_by_section
    except Exception as e:  # noqa: BLE001
        st.error(f"Error loading subject: {e}")
        return {}

# --- Styling helpers reused ---
def set_custom_styles():
    st.markdown(
        """
        <style>
        .stForm {background-color: rgba(0,0,0,0.75); padding:24px; border-radius:14px;}
        .otp-info {color:#63b3ed; font-size:0.9rem;}
        
        /* Hide scrollbars (keep scrolling enabled) */
        /* Chrome, Safari, Edge */
        ::-webkit-scrollbar { width: 0px; height: 0px; background: transparent; }
        /* Firefox */
        html, body { scrollbar-width: none; }
        /* IE/Edge Legacy */
        body { -ms-overflow-style: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def apply_local_background(image_name: str = "Image/background_1.png"):
    background_path = Path(__file__).resolve().parent / image_name
    try:
        encoded = base64.b64encode(background_path.read_bytes()).decode()
    except FileNotFoundError:
        return
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{encoded}");
            background-size: cover; background-position: center; background-attachment: fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# --- Two-stage login UI ---
def login_flow():
    st.header("Teacher Login")
    if st.session_state.login_stage == "credentials":
        with st.form("credentials_form"):
            nic = st.text_input("NIC", placeholder="National ID Number")
            birthdate = st.text_input("Birthdate (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
            appointment = st.text_input("First Appointment Date (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
            submitted = st.form_submit_button("Verify & Send OTP")
            if submitted:
                if not (nic and birthdate and appointment):
                    st.error("All fields required.")
                    return
                teacher = get_teacher_with_meta(nic, birthdate, appointment)
                if not teacher:
                    st.error("❌ No matching teacher record. Check details.")
                    return
                if not teacher["mobile"]:
                    st.error("❌ Mobile number missing in records. Contact admin.")
                    return
                normalized_mobile = normalize_sri_lanka_mobile(teacher["mobile"])
                if not normalized_mobile:
                    st.error("❌ Invalid or non-Sri Lankan mobile format in record. Please contact administration.")
                    return
                # Send OTP via Text.lk (server generates OTP and returns it)
                ok, result = send_textlk_otp(normalized_mobile, length=6)
                if not ok:
                    st.error(f"Failed to send OTP: {result}")
                    if OTP_DEBUG:
                        st.caption("OTP debug: Text.lk error above.")
                    return
                # Store OTP from API response for verification
                st.session_state.otp_code = result
                st.session_state.otp_expiry = datetime.utcnow() + timedelta(minutes=5)
                st.session_state.mobile_number = normalized_mobile
                st.session_state.teacher_name = teacher["name"]
                st.session_state.teacher_nic = teacher["nic"]
                st.session_state.teacher_title = teacher["title"]
                st.session_state.otp_sent = True
                st.session_state.login_stage = "otp"
                st.success("✅ OTP sent to your registered mobile number.")
                st.rerun()
    elif st.session_state.login_stage == "otp":
        # st.session_state.mobile_number is normalized +94XXXXXXXXX
        mobile = st.session_state.mobile_number or ""
        if mobile.startswith("+94") and len(mobile) == 12:  # +94 + 9 digits
            # Show +94 7X ** ** *678 (last 3 digits visible)
            masked = f"+94 {mobile[3:5]}** ** *{mobile[-3:]}"
        else:
            masked = "(hidden)"
        st.info(f"An OTP was sent to your registered mobile: {masked}")
        with st.form("otp_form"):
            otp_input = st.text_input("Enter 6-digit OTP", max_chars=6)
            verify = st.form_submit_button("Verify OTP")
            if verify:
                if not st.session_state.otp_code or not st.session_state.otp_expiry:
                    st.error("OTP session expired. Restart login.")
                    st.session_state.login_stage = "credentials"
                    st.rerun()
                if datetime.utcnow() > st.session_state.otp_expiry:
                    st.error("❌ OTP expired. Please request a new one.")
                    st.session_state.login_stage = "credentials"
                    st.rerun()
                if otp_input != st.session_state.otp_code:
                    st.error("❌ Incorrect OTP.")
                    return
                st.session_state.logged_in = True
                st.success(f"Welcome {st.session_state.teacher_title} {st.session_state.teacher_name} ✨")
                # Clear sensitive OTP
                st.session_state.otp_code = None
                st.session_state.otp_expiry = None
                st.session_state.login_stage = "authenticated"
                st.rerun()
        if st.button("Resend OTP"):
            ok, result = send_textlk_otp(st.session_state.mobile_number, length=6)
            if ok:
                st.session_state.otp_code = result
                st.session_state.otp_expiry = datetime.utcnow() + timedelta(minutes=5)
                st.info("A new OTP has been sent.")
            else:
                st.error(f"Failed to resend OTP: {result}")

# --- Original submission page trimmed for brevity (reuse from main app) ---
def submission_page():
    st.subheader("Transfer Request Form")
    schools = get_schools()
    st.markdown("### Teaching Sections")
    section_options = ["Primary", "Secondary", "A/L_General", "A/L_Arts", "A/L_Commerce", "A/L_Technology", "A/L_Science"]
    section = st.multiselect("Select Section(s)", section_options)

    subjects_by_section = get_subjects(section)
    selected_subjects = []
    for sec, subs in subjects_by_section.items():
        chosen = st.multiselect(f"Select {sec} subjects", options=subs, key=f"subj_multi_{sec}")
        selected_subjects.extend(chosen)
    st.session_state.selected_subjects = selected_subjects

    st.markdown("### Transfer Request Details")
    with st.form("submission_form"):
        address = st.text_input("Current Address")
        reason = st.text_area("Reasons for Transfer Request")
        st.markdown("#### School Preferences (up to 5)")
        school_choices = []
        for i in range(5):
            choice = st.selectbox(f"Preference {i+1}", ["-- None --"] + schools, key=f"school_pref_{i}")
            if choice != "-- None --":
                school_choices.append(choice)
        submitted = st.form_submit_button("Submit Transfer Request")
        if submitted:
            if not selected_subjects or not address or not reason.strip():
                st.error("Fill all required fields.")
                st.stop()
            if len(school_choices) == 0:
                st.error("At least one school required.")
                st.stop()
            if len(school_choices) != len(set(school_choices)):
                st.error("Duplicate schools detected.")
                st.stop()
            
            # ✅ Strict Sri Lanka address validation
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": address,
                "key": GOOGLE_API_KEY,
                "components": "country:LK",
                "region": "LK"
            }
            response = requests.get(url, params=params).json()

            if response.get("status") != "OK":
                st.error("❌ Google could not validate the address. Please enter a more complete Sri Lankan address.")
                st.stop()

            results = response.get("results", [])
            if not results:
                st.error("❌ No results found. Please enter a valid Sri Lankan address (e.g., city, road, or area).")
                st.stop()

            first_result = results[0]
            formatted_address = first_result.get("formatted_address", "")
            address_components = first_result.get("address_components", [])
            geometry = first_result.get("geometry", {}).get("location", {})

            # Extract country
            country_component = next(
                (c for c in address_components if "country" in c.get("types", [])),
                {}
            )
            country_code = country_component.get("short_name")

            # Validate location details
            lat, lng = geometry.get("lat"), geometry.get("lng")

            if country_code != "LK":
                st.error(f"❌ This address is located in another country ({country_code}). Please enter a Sri Lankan address.")
                st.stop()
            if lat is None or lng is None:
                st.error("❌ Unable to determine exact location. Please refine your address.")
                st.stop()
            if not (5.9 <= lat <= 9.9 and 79.4 <= lng <= 82.1):
                st.error("❌ Address coordinates are outside Sri Lanka's boundaries. Please enter a valid Sri Lankan address.")
                st.stop()

            # Text similarity check
            similarity = difflib.SequenceMatcher(None, address.lower(), formatted_address.lower()).ratio()
            if similarity < 0.25:
                st.error("❌ The entered text doesn't match any known Sri Lankan location. Please check your spelling or enter a clearer address.")
                st.stop()

            # Ensure formatted address ends with Sri Lanka
            if not formatted_address.lower().strip().endswith("sri lanka"):
                st.error("❌ Address must be within Sri Lanka. Please enter a valid Sri Lankan address.")
                st.stop()

            # All good ✅
            validated_address = formatted_address    
            # (Skipping address validation for brevity; reuse from original if needed)
            current_month = datetime.now().strftime("%Y%m")
            nic_safe = re.sub(r'[^a-zA-Z0-9_-]', '_', st.session_state.teacher_nic)
            file_name = f"{nic_safe}_{current_month}.parquet"
            bronze_path = f"abfs://{BRONZE_CONTAINER}@{AZURE_STORAGE_ACCOUNT}.dfs.core.windows.net/Vacancy_Details/"
            fs = adlfs.AzureBlobFileSystem(account_name=AZURE_STORAGE_ACCOUNT, account_key=AZURE_STORAGE_KEY)
            if fs.exists(f"{bronze_path}{file_name}"):
                st.error("You already submitted this month.")
            else:
                data = pd.DataFrame([
                    {
                        "NIC": st.session_state.teacher_nic,
                        "Teacher_Name": st.session_state.teacher_name,
                        "Section": ",".join(section),
                        "Subjects": ",".join(selected_subjects),
                        "Validated_Address": validated_address,
                        "School_Preferences": ",".join(school_choices),
                        "Reason": reason,
                        "Submitted_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                ])
                data.to_parquet(f"{bronze_path}{file_name}", index=False, filesystem=fs)
                st.success("✅ Form submitted successfully!")
                st.balloons()

# --- Page config & styling ---
st.set_page_config(page_title="Teacher Portal OTP", page_icon="👨‍🏫", layout="centered", initial_sidebar_state="collapsed")
set_custom_styles()
apply_local_background()

# --- Main Flow ---
if not st.session_state.logged_in:
    login_flow()
else:
    submission_page()

with st.sidebar:
    st.title("Portal (OTP)")
    if st.session_state.logged_in:
        st.write(f"Logged in as: {st.session_state.teacher_title} {st.session_state.teacher_name}")
        if st.button("Logout"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    st.markdown("---")
    st.markdown("Your OTP session will expire in 5 minutes of inactivity.")
