import os
import base64
from pathlib import Path
from io import BytesIO

import pandas as pd
import pyodbc
import streamlit as st
from dotenv import load_dotenv

# --- Load env vars ---
load_dotenv()
SERVER = os.getenv("SYNAPSE_SERVER")
DATABASE = os.getenv("SYNAPSE_DB")
USERNAME = os.getenv("SYNAPSE_USER")
PASSWORD = os.getenv("SYNAPSE_PASS")
DRIVER = "ODBC Driver 17 for SQL Server"


# ---------------------------
# DB Connection
# ---------------------------
def get_connection():
    """Create a connection to Azure Synapse using ODBC"""
    return pyodbc.connect(
        f"Driver={{{DRIVER}}};"
        f"Server={SERVER};"
        f"Database={DATABASE};"
        f"Uid={USERNAME};"
        f"Pwd={PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=40;"
    )


# ---------------------------
# Validate Admin Login
# ---------------------------
def validate_admin(nic: str, birthdate: str) -> bool:
    """Check if NIC + BirthDate exists in gold.ext_admin"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM gold.ext_admin WHERE NIC = ? AND Birth_Date = ?",
        (nic, birthdate),
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None


# ---------------------------
# Load Data Functions
# ---------------------------
def load_vacancy() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM gold.ext_vacancy", conn)
    conn.close()
    return df


def load_matches(table_name: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df


def get_kpis():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM gold.ext_vacancy WHERE Eligible = 1")
    eligible_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM gold.ext_vacancy WHERE Eligible = 0")
    noneligible_count = cursor.fetchone()[0]

    cursor.execute("SELECT Division, COUNT(*) FROM gold.ext_vacancy GROUP BY Division")
    division_data = cursor.fetchall()
    division_data = [(row[0], row[1]) for row in division_data]

    conn.close()
    return eligible_count, noneligible_count, division_data


# ---------------------------
# Export Helpers
# ---------------------------
def convert_df_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return output.getvalue()


# ---------------------------
# Formatting Helpers
# ---------------------------
def format_eligibility(df: pd.DataFrame) -> pd.DataFrame:
    """Convert eligibility columns into ✅ / ❌"""
    df = df.copy()
    for col in df.columns:
        if "Eligible" in col:
            df[col] = df[col].apply(lambda x: "✅" if x in [1, True] else "❌")
    return df


# ---------------------------
# UI Helpers
# ---------------------------
def set_custom_styles():
    """Apply glassmorphism styling and modern typography."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');

        .stApp {
            font-family: 'Poppins', sans-serif;
        }

        .glass-card {
            background: rgba(0, 0, 0, 0.7);
            border-radius: 18px;
            padding: 28px 32px;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.25);
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            color: #f7fafc;
        }

        .main-card {
            margin-top: 12px;
        }

        .login-card {
            padding: 36px 42px;
        }

        .hero-title {
            text-align: center;
            color: #ebf4ff;
            margin-bottom: 1.5rem;
            text-shadow: 0 4px 20px rgba(59, 130, 246, 0.45);
        }

        .hero-title h1 {
            font-weight: 700;
            font-size: 2.6rem;
            margin-bottom: 0.25rem;
        }

        .hero-title p {
            font-size: 1.05rem;
            opacity: 0.85;
        }

        .section-title {
            color: #e6fffa;
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }

        .section-subtitle {
            color: #bee3f8;
            font-size: 1.3rem;
            margin-top: 1.5rem;
        }

        .divider {
            height: 1px;
            background: linear-gradient(90deg, rgba(255,255,255,0.05), rgba(148, 187, 233, 0.4), rgba(255,255,255,0.05));
            margin: 1.8rem 0;
        }

        .stTextInput > div > div > input,
        .stSelectbox > div > div > select,
        .stMultiselect > div > div > div > input,
        .stDateInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stRadio > div,
        .stCheckbox > label,
        .stDownloadButton,
        .stFileUploader > div {
            background-color: rgba(15, 23, 42, 0.65) !important;
            color: #e2e8f0 !important;
            border-radius: 10px !important;
            border: 1px solid rgba(148, 163, 184, 0.4) !important;
        }

        .stButton > button {
            background: linear-gradient(135deg, #63b3ed, #3182ce);
            color: white;
            font-weight: 600;
            border: none;
            border-radius: 12px;
            padding: 0.6rem 1.8rem;
            transition: all 0.25s ease;
            letter-spacing: 0.3px;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 12px 25px rgba(66, 153, 225, 0.35);
        }

        div[data-testid="stMetricValue"] {
            color: #f8fafc;
        }

        div[data-testid="stMetricDelta"] svg {
            fill: #f8fafc;
        }

        .metric-card {
            padding: 16px;
            border-radius: 16px;
            background: linear-gradient(145deg, rgba(14, 116, 144, 0.65), rgba(30, 64, 175, 0.65));
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(10px);
        }
        /* New dashboard metric layout */
        .metric-row {
            display: flex;
            gap: 18px;
            flex-wrap: wrap;
            margin: 10px 0 8px 0;
        }
        .metric-box {
            flex: 1 1 220px;
            background: linear-gradient(145deg, rgba(30,41,59,0.78), rgba(15,23,42,0.78));
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 18px;
            padding: 18px 20px 16px 20px;
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            position: relative;
            overflow: hidden;
        }
        .metric-box:before {
            content: "";
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at 25% 20%, rgba(96,165,250,0.18), transparent 70%);
            pointer-events: none;
        }
        .metric-label {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #93c5fd;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .metric-value {
            font-size: 2.05rem;
            font-weight: 700;
            color: #f1f5f9;
            line-height: 1.1;
            text-shadow: 0 3px 14px rgba(0,0,0,0.45);
        }

        [data-testid="stSidebar"] {
            background: rgba(10, 25, 47, 0.7);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        .sidebar-divider {
            height: 1px;
            background: rgba(148, 163, 184, 0.3);
            margin: 1rem 0;
        }

        /* New dark blur form style (updated to also catch native stForm container) */
        div[data-testid="stForm"],
        div[data-testid="stForm"][aria-label="admin_login_form"],
        .dark-blur-form {
            background: rgba(10,15,30,0.60) !important;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 22px;
            padding: 42px 46px 34px 46px;
            backdrop-filter: blur(18px) saturate(135%);
            -webkit-backdrop-filter: blur(18px) saturate(135%);
            box-shadow: 0 12px 32px -4px rgba(0,0,0,0.55), 0 2px 6px rgba(0,0,0,0.35);
        }
        /* Inner form layout adjustment (avoid nested extra padding) */
        div[data-testid="stForm"] form {
            padding-top: 4px;
        }
        /* Headings inside forms */
        div[data-testid="stForm"] h3 {
            color: #e2eaf7 !important;
            letter-spacing: 0.5px;
            font-weight: 600;
            text-align: center;
            margin-top: 0;
        }
        /* Buttons full-width inside the form */
        div[data-testid="stForm"] .stButton > button {
            width: 100%;
            margin-top: 4px;
        }
        /* Focus styling */
        div[data-testid="stForm"] input:focus {
            outline: 1px solid #3b82f6 !important;
            box-shadow: 0 0 0 1px #3b82f6, 0 0 0 4px rgba(59,130,246,0.25);
            transition: box-shadow 0.25s ease;
        }

        .dataframe thead tr,
        .dataframe tbody tr {
            background: rgba(15, 23, 42, 0.75) !important;
            color: #f7fafc !important;
        }

        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-thumb {
            background: rgba(148, 163, 184, 0.45);
            border-radius: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_local_background(image_name: str = "Image/admin.png"):
    """Add a blurred, fixed background image from the local app directory."""
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
            background-color: rgba(0, 0, 0, 0.35); /* aligned with app.py */
            backdrop-filter: blur(0px);
            -webkit-backdrop-filter: blur(0px);
            z-index: -1;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------
# Layout Helpers
# ---------------------------
def render_login():
    st.markdown(
        """
        <div class="hero-title">
            <h1>Admin Control Center</h1>
            <p>Secure access for provincial administrators</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("admin_login_form"):
            st.markdown("<h3>Enter Credentials</h3>", unsafe_allow_html=True)
            nic = st.text_input("NIC", placeholder="Enter administrator NIC")
            birthdate = st.text_input("Birth Date (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
            submit = st.form_submit_button("Access Dashboard", use_container_width=True)

    if submit:
        if not nic or not birthdate:
            st.error("❌ Please fill both NIC and Birth Date.")
        elif validate_admin(nic, birthdate):
            st.session_state.logged_in = True
            st.session_state.nic = nic
            st.success("✅ Login successful. Redirecting…")
            st.rerun()
        else:
            st.error("❌ Invalid NIC or Birth Date. Please try again.")


def render_dashboard():
    eligible_count, noneligible_count, division_data = get_kpis()

    # Header + KPIs card
    st.markdown(
        f"""
        <div class="glass-card main-card">
            <div class='section-title'>📖 Teacher Transfer Dashboard</div>
            <p style='color:#cbd5f5; margin-bottom: 1.2rem;'>Real-time overview of transfer eligibility across the province.</p>
            <div class="metric-row">
                <div class="metric-box">
                    <div class="metric-label">Eligible Teachers</div>
                    <div class="metric-value">{eligible_count}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Non-Eligible Teachers</div>
                    <div class="metric-value">{noneligible_count}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Divisions</div>
                    <div class="metric-value">{len(division_data)}</div>
                </div>
            </div>
            <div class='divider'></div>
            <details style="margin-top:4px;">
                <summary style="cursor:pointer; color:#93c5fd; font-weight:600; margin-bottom:10px;">📌 Division-wise Teacher Count</summary>
                <div style="margin-top:14px;">
        """,
        unsafe_allow_html=True,
    )

    # Division table (inside first card)
    div_df = pd.DataFrame(division_data, columns=["Division", "TeacherCount"])
    st.dataframe(div_df, use_container_width=True)

    # Close details and first card, open second card
    st.markdown(
        """
                </div>
            </details>
        </div>
        <div class="glass-card main-card" style="margin-top:18px;">
            <div class='section-subtitle' style="margin-top:0;">📋 Vacancy Details</div>
        """,
        unsafe_allow_html=True,
    )

    # Vacancy data + export
    vac_df = load_vacancy()
    filter_options = ["Eligible", "Not Eligible"]
    selected_filters = st.multiselect(
        "Filter Teachers",
        filter_options,
        default=["Eligible"],
        help="Choose which teacher groups to display",
    )
    if "Eligible" in selected_filters and "Not Eligible" not in selected_filters:
        filtered_df = vac_df[vac_df["Eligible"] == True]
    elif "Not Eligible" in selected_filters and "Eligible" not in selected_filters:
        filtered_df = vac_df[vac_df["Eligible"] == False]
    else:
        filtered_df = vac_df

    st.dataframe(format_eligibility(filtered_df), use_container_width=True, height=420)

    st.markdown("<div class='section-subtitle'>📂 Export Data</div>", unsafe_allow_html=True)
    st.download_button(
        "⬇️ Download Excel",
        convert_df_excel(filtered_df),
        "vacancy_details.xlsx",
        "application/vnd.ms-excel",
        use_container_width=True,
    )

    # Close second card
    st.markdown("</div>", unsafe_allow_html=True)


def render_matching():
    # Open a single glass-card wrapper so the border applies to the whole section
    st.markdown(
        """
        <div class='glass-card main-card'>
            <div class='section-title'>🤝 Teacher Transfer Matching</div>
            <p style='color:#cbd5f5; margin-bottom: 1.5rem;'>Explore reciprocal and top-ranked matches for each teacher.</p>
        """,
        unsafe_allow_html=True,
    )

    vac_df = load_vacancy()
    match_col1, match_col2 = st.columns(2)
    with match_col1:
        match_type = st.radio(
            "Match Type",
            ["Reciprocal Matches", "Top-10 Options"],
            horizontal=True,
        )
    with match_col2:
        eligibility_filter = st.radio(
            "Eligibility",
            ["Eligible", "Not Eligible"],
            horizontal=True,
        )

    if match_type == "Reciprocal Matches":
        df = load_matches("gold.ext_reciprocal_match")
        key_col = "TeacherA_NIC"
        if eligibility_filter == "Eligible":
            df = df[(df["TeacherA_Eligible"] == 1) & (df["TeacherB_Eligible"] == 1)]
        else:
            df = df[(df["TeacherA_Eligible"] == 0) & (df["TeacherB_Eligible"] == 1)]
    else:
        df = load_matches("gold.ext_top_10_match")
        key_col = "Teacher_NIC"
        if eligibility_filter == "Eligible":
            df = df[(df["Teacher_Eligible"] == 1) & (df["Candidate_Eligible"] == 1)]
        else:
            df = df[(df["Teacher_Eligible"] == 0) & (df["Candidate_Eligible"] == 1)]

    if eligibility_filter == "Eligible":
        teacher_list = vac_df[vac_df["Eligible"] == True][["NIC", "Teacher_Name"]]
    else:
        teacher_list = vac_df[vac_df["Eligible"] == False][["NIC", "Teacher_Name"]]

    teacher_options = (
        teacher_list["NIC"] + " - " + teacher_list["Teacher_Name"]
    ).tolist()

    if not teacher_options:
        st.info("ℹ️ No teachers available for the selected eligibility filter.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    teacher_choice = st.selectbox("Select Teacher", teacher_options)
    teacher_nic = teacher_choice.split(" - ")[0]

    matches_for_teacher = df[df[key_col] == teacher_nic]

    if matches_for_teacher.empty:
        st.info("ℹ️ No matches found for this teacher.")
    else:
        st.dataframe(format_eligibility(matches_for_teacher), use_container_width=True, height=420)
        st.markdown("<div class='section-subtitle'>📂 Export Matches</div>", unsafe_allow_html=True)
        st.download_button(
            "⬇️ Download Excel",
            convert_df_excel(matches_for_teacher),
            "matches.xlsx",
            "application/vnd.ms-excel",
            use_container_width=True,
        )

    # Close glass-card wrapper
    st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar():
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/teacher.png", width=85)
        st.markdown(
            """
            <h2 style="color:#e2e8f0;">Admin Hub</h2>
            <p style="color:#cbd5f5;">Monitor transfer eligibility and manage teacher matching effortlessly.</p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)

        page = st.radio(
            "Navigation",
            ["📊 Dashboard", "🤝 Matching"],
            index=0,
            label_visibility="collapsed",
        )

        st.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)
        if st.button("Log out", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.nic = None
            st.rerun()

        st.markdown(
            """
            <p style="color:#94a3b8; font-size:0.85rem; margin-top:2rem;">
            📞 Support: +94 11 2784812<br/>
            📧 Email: admin-support@education.gov.lk
            </p>
            """,
            unsafe_allow_html=True,
        )
    return page


# ---------------------------
# Application Entry Point
# ---------------------------
st.set_page_config(
    page_title="Teacher Transfer Admin Portal",
    page_icon="👨‍⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

set_custom_styles()
apply_local_background()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.nic = None

if not st.session_state.logged_in:
    render_login()
else:
    selected_page = render_sidebar()
    if selected_page == "📊 Dashboard":
        render_dashboard()
    else:
        render_matching()

