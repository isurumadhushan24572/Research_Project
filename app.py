import streamlit as st
from sqlalchemy import create_engine, text, bindparam
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime
import adlfs
import re
import requests
import difflib  # Used for address similarity checking
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

# --- Helper Functions for UI Enhancement ---
def add_bg_from_url(url):
    """Add background image from URL with blur effect"""
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("{url}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            backdrop-filter: blur(10px); /* Add blur effect */
            -webkit-backdrop-filter: blur(10px); /* For Safari compatibility */
        }}
        
        /* Add an overlay to enhance blur effect */
        .stApp:before {{
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(255, 255, 255, 0.3);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            z-index: -1;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

def set_custom_styles():
    """Set custom styles for a more attractive UI with blur effects"""
    st.markdown("""
        <style>
        /* Main container styling with blur effect */
        .main {
            background-color: rgba(255, 255, 255, 0.7);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
        }
        
        /* Header styling */
        h1 {
            color: #1a365d;
            font-size: 2.6rem;
            text-align: center;
            margin-bottom: 25px;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 700;
        }
        
        /* Subheader styling */
        h2, h3 {
            color: #2b6cb0;
            margin-top: 22px;
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 600;
        }
        
        /* Form styling with black background */
        .stForm {
            background-color: rgba(0, 0, 0, 0.8);
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
            margin-bottom: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            color: white;
        }
        
        .stForm:hover {
            background-color: rgba(0, 0, 0, 0.85);
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.3);
        }
        
        /* Button styling */
        .stButton>button {
            background: linear-gradient(135deg, #4299e1, #3182ce);
            color: white;
            font-weight: bold;
            border: none;
            border-radius: 8px;
            padding: 12px 28px;
            text-align: center;
            transition: all 0.3s ease;
            letter-spacing: 0.5px;
        }
        
        .stButton>button:hover {
            background: linear-gradient(135deg, #3182ce, #2c5282);
            box-shadow: 0 8px 20px rgba(49, 130, 206, 0.3);
            transform: translateY(-2px);
        }
        
        /* Input styling - adjusted for black form background */
        .stTextInput>div>div>input, .stTextArea>div>div>textarea {
            border-radius: 8px;
            border: 1px solid #444;
            padding: 10px 14px;
            background-color: rgba(30, 30, 30, 0.8);
            backdrop-filter: blur(5px);
            -webkit-backdrop-filter: blur(5px);
            color: white;
        }
        
        /* Label styling for dark background */
        .stForm label, .stForm .st-ae, .stForm p {
            color: #ddd !important;
        }
        
        /* Success message styling */
        .element-container div[data-testid="stDecoration"] div[role="alert"][data-baseweb="notification"] {
            border-radius: 10px;
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
        }
        
        /* Card styling with black background */
        .card {
            background-color: rgba(0, 0, 0, 0.8);
            border-radius: 16px;
            padding: 25px;
            margin: 16px 0;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: white;
        }
        
        /* Image container with professional styling */
        .image-container {
            display: flex;
            justify-content: center;
            margin: 25px 0;
        }
        
        /* Welcome banner with glass effect */
        .welcome-banner {
            background: linear-gradient(135deg, rgba(49, 130, 206, 0.8), rgba(43, 108, 176, 0.8));
            color: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 25px;
            text-align: center;
            box-shadow: 0 8px 20px rgba(43, 108, 176, 0.25);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
        }
        
        /* Footer */
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 15px;
            font-size: 0.9rem;
            color: #4a5568;
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(247, 250, 252, 0.3);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(160, 174, 192, 0.5);
            border-radius: 10px;
        }
        
        /* Image carousel styling */
        .image-carousel {
            display: flex;
            overflow-x: auto;
            padding: 15px 0;
            gap: 20px;
            margin-bottom: 25px;
            scroll-behavior: smooth;
        }
        </style>
    """, unsafe_allow_html=True)

def display_login_page():
    """Display the login page with glass morphism effect"""
    col1, col2, col3 = st.columns([1, 4, 1])
    
    with col2:
        st.markdown("""
            <div style="text-align: center; padding: 20px;">
                <h1 style="color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.1);">Teacher Login Portal</h1>
            </div>
        """, unsafe_allow_html=True)
        
        # Top image removed as requested
        
        with st.form("login_form"):
            st.markdown("<h3 style='text-align: center; margin-bottom: 20px; color: white;'>Enter Your Credentials</h3>", unsafe_allow_html=True)
            nic = st.text_input("Enter NIC", placeholder="National ID Number")
            birthdate = st.text_input("Enter Birthdate (YYYY-MM-DD)", type="password", placeholder="YYYY-MM-DD")
            
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                submit = st.form_submit_button("Login")
                
            if submit:
                teacher = get_teacher(nic, birthdate)
                if teacher:
                    st.session_state.logged_in = True
                    st.session_state.teacher_name = teacher["name"]
                    st.session_state.teacher_nic = teacher["nic"]
                    st.session_state.teacher_title = teacher["title"]
                    st.success(f"✅ Welcome {teacher['title']} {teacher['name']}! Redirecting...")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ Invalid NIC or Birthdate")
        
        # st.markdown("""
        #     <div class="footer">
        #         <p>© 2025 Sri Lankan Provincial Education Department</p>
        #     </div>
        # """, unsafe_allow_html=True)

def display_submission_page():
    """Display the submission page with better UI"""
    st.markdown(f"""
        <div class="welcome-banner">
            <h2 style="font-size: 1.8rem; margin-bottom: 10px;">Welcome, {st.session_state.teacher_title} {st.session_state.teacher_name} 👋</h2>
            <p style="font-size: 1.1rem; opacity: 0.9;">Please complete your teacher transfer request form below</p>
            <div style="width: 70%; height: 4px; background: rgba(255,255,255,0.3); margin: 10px auto 0 auto; border-radius: 2px;"></div>
        </div>
    """, unsafe_allow_html=True)
    
    # Image carousel removed as requested
    
    # Main form with glass morphism effect
    # st.markdown("<div class='card'>", unsafe_allow_html=True)
    
    schools = get_schools()

    # --- Section selection with better UI ---
    st.markdown("<h3 style='color: white;'>📚 Teaching Sections</h3>", unsafe_allow_html=True)
    section_options = ["Primary", "Secondary", "A/L_General", "A/L_Arts",
                      "A/L_Commerce", "A/L_Technology", "A/L_Science"]
    section = st.multiselect("Select Section(s)", section_options, 
                            help="Choose all sections that you teach")

    # --- Subjects (grouped by section) with better UI ---
    st.markdown("<h3 style='color: white;'>📘 Teaching Subjects</h3>", unsafe_allow_html=True)
    subjects_by_section = get_subjects(section)
    selected_subjects = []

    if subjects_by_section:
        for sec, subs in subjects_by_section.items():
            st.markdown(f"<p style='font-weight: bold; color: #4da6ff;'>{sec} Subjects:</p>", unsafe_allow_html=True)
            chosen = st.multiselect(f"Select {sec} subjects", options=subs, default=[], key=f"subj_multi_{sec}")
            selected_subjects.extend(chosen)
    else:
        st.info("👆 Please select at least one section to view available subjects")

    st.session_state.selected_subjects = selected_subjects
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Transfer request form
    # st.markdown("<div class='card' style='margin-top: 20px;'>", unsafe_allow_html=True)
    st.markdown("<h3 style='color: white;'> 📃Transfer Request Details</h3>", unsafe_allow_html=True)
    
    with st.form("submission_form"):
        address = st.text_input("Current Address", placeholder="Enter your complete Sri Lankan address")
        Reason = st.text_area("Reasons for Transfer Request", placeholder="Please explain why you are requesting a transfer...")

        st.markdown("<h4 style='color: white;'>🎯 School Preferences</h4><p style='color: #ccc;'>Select up to 5 schools in order of preference</p>", unsafe_allow_html=True)
        
        # --- School Preferences with better UI ---
        school_choices = []
        cols = st.columns(2)
        
        for i in range(5):
            col_idx = i % 2
            with cols[col_idx]:
                choice = st.selectbox(
                    f"Preference {i+1}",
                    ["-- None --"] + schools,
                    key=f"school_pref_{i}"
                )
                if choice != "-- None --":
                    school_choices.append(choice)

        submitted = st.form_submit_button("Submit Transfer Request")
        
        if submitted:
            # --- Basic validation ---
            if not st.session_state.selected_subjects or not address or not Reason.strip():
                st.error("❌ Please fill all required fields before submitting.")
                st.stop()
            if len(school_choices) == 0:
                st.error("❌ Please select at least one school.")
                st.stop()
            if len(school_choices) != len(set(school_choices)):
                st.error("❌ Duplicate schools selected. Each preference must be unique.")
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

            # --- Save to Azure Blob ---
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
                data = pd.DataFrame([{
                    "NIC": st.session_state.teacher_nic,
                    "Teacher_Name": st.session_state.teacher_name,
                    "Section": ",".join(section),
                    "Subjects": ",".join(st.session_state.selected_subjects),
                    "Validated_Address": validated_address,
                    "School_Preferences": ",".join(school_choices),
                    "Reason": Reason,
                    "Submitted_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])

                data.to_parquet(f"{bronze_path}{file_name}", index=False, filesystem=fs)
                st.success("✅ Form submitted and saved successfully!")
                st.balloons()

    st.markdown("</div>", unsafe_allow_html=True)
    
    # Footer
    # st.markdown("""
    #     <div class="footer">
    #         <hr style="background-image: linear-gradient(to right, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0));">
    #         <p style="color: #aaa;">© 2025 Sri Lankan Provincial Education Department | Teacher Transfer Portal</p>
    #     </div>
    # """, unsafe_allow_html=True)


# --- Streamlit page config ---
st.set_page_config(
    page_title="Teacher Portal", 
    page_icon="👨‍🏫", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Apply custom styling ---
set_custom_styles()

# --- Add background with blur effect ---
def apply_local_background(image_name: str = "Image/background_1.png"):
    background_path = Path(__file__).resolve().parent / image_name
    try:
        encoded = base64.b64encode(background_path.read_bytes()).decode()
    except FileNotFoundError:
        st.warning("⚠️ Background image missing. Please add background_1.png to the app folder.")
        return
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            backdrop-filter: blur(0px);
            -webkit-backdrop-filter: blur(0px);
        }}
        .stApp:before {{
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.35);
            backdrop-filter: blur(0px);
            -webkit-backdrop-filter: blur(0px);
            z-index: -1;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

apply_local_background()

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
                WHERE NIC = :nic AND Birth_Date = :birthdate AND Type = 'Provintial'
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
            query = text("SELECT DISTINCT School_Name FROM gold.ext_school WHERE Type = 'Provintial'")
            result = conn.execute(query).fetchall()
            return [row.School_Name for row in result]
    except Exception as e:
        st.error(f"Error loading schools: {e}")
        return []

# --- Helper: get subject list (optimized) ---
def get_subjects(section: list):
    if engine is None or not section:
        return {}
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT DISTINCT SECTION, SUBJECT
                FROM gold.ext_subject
                WHERE SECTION IN :section
                ORDER BY SECTION, SUBJECT
            """).bindparams(bindparam("section", expanding=True))
            result = conn.execute(query, {"section": section}).fetchall()
            subjects_by_section = {}
            for row in result:
                subjects_by_section.setdefault(row.SECTION, []).append(row.SUBJECT)
            return subjects_by_section
    except Exception as e:
        st.error(f"Error loading subject: {e}")
        return {}

# --- Main app flow ---
if not st.session_state.logged_in:
    display_login_page()
else:
    display_submission_page()

# Add a sidebar with app info
with st.sidebar:
    st.title("Teacher Transfer Portal")
    st.markdown("""
    This portal allows provincial teachers to:
    
    - Submit transfer requests
    - Select preferred schools
    - Specify teaching sections and subjects
    
    Your information is securely stored and processed by the Provincial Education Department.
    """)
    
    st.markdown("---")
    st.write("Need help? Contact support:")
    st.write("📧 support@education.gov.lk")
    st.write("☎️ +94 11 2784812")