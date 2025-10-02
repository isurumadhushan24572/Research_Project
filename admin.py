import streamlit as st
import pandas as pd
import pyodbc
from dotenv import load_dotenv
import os
from io import BytesIO

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
    conn = pyodbc.connect(
        f"Driver={{{DRIVER}}};"
        f"Server={SERVER};"
        f"Database={DATABASE};"
        f"Uid={USERNAME};"
        f"Pwd={PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=40;"
    )
    return conn 

# ---------------------------
# Validate Admin Login
# ---------------------------
def validate_admin(nic: str, birthdate: str) -> bool:
    """Check if NIC + BirthDate exists in gold.admin"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM gold.ext_admin WHERE NIC = ? AND Birth_Date = ?", (nic, birthdate))
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
# Streamlit Page Config
# ---------------------------
st.set_page_config(page_title="Teacher Transfer Dashboard", page_icon="👨‍⚖️", layout="wide")

# ---------------------------
# Session State
# ---------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------------------
# Login Page
# ---------------------------
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align:center;'>🔑 Admin Login</h2>", unsafe_allow_html=True)
    st.write("Please enter your NIC and Birth Date to access the system.")

    nic = st.text_input("NIC")
    birthdate = st.text_input("BirthDate (YYYY-MM-DD)",)

    if st.button("Login", use_container_width=True):
        if validate_admin(nic, birthdate):
            st.session_state.logged_in = True
            st.session_state.nic = nic
            st.success("✅ Login successful")
            st.rerun()
        else:
            st.error("❌ Invalid NIC or BirthDate")

# ---------------------------
# After Login
# ---------------------------
else:
    # Sidebar Navigation
    st.sidebar.image("https://img.icons8.com/color/96/teacher.png", width=80)
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["📊 Dashboard", "🤝 Matching"])

    # ---------------------------
    # Page 1: Dashboard
    # ---------------------------
    if page == "📊 Dashboard":
        st.markdown("## 📊 Teacher Transfer Dashboard")

        eligible_count, noneligible_count, division_data = get_kpis()

        # KPI Cards
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Eligible Teachers", eligible_count)
        col2.metric("❌ Non-Eligible Teachers", noneligible_count)
        col3.metric("🏫 Divisions", len(division_data))

        with st.expander("📌 Division-wise Teacher Count"):
            div_df = pd.DataFrame(division_data, columns=["Division", "TeacherCount"])
            st.dataframe(div_df, use_container_width=True)

        # Vacancy Details
        st.markdown("---")
        st.subheader("📋 Vacancy Details")
        vac_df = load_vacancy()

        filter_options = ["Eligible", "Not Eligible"]
        selected_filters = st.multiselect("Filter Teachers", filter_options, default=["Eligible"])

        if "Eligible" in selected_filters and "Not Eligible" not in selected_filters:
            filtered_df = vac_df[vac_df["Eligible"] == True]
        elif "Not Eligible" in selected_filters and "Eligible" not in selected_filters:
            filtered_df = vac_df[vac_df["Eligible"] == False]
        else:
            filtered_df = vac_df

        st.dataframe(format_eligibility(filtered_df), use_container_width=True)

        # Export
        st.markdown("### 📂 Export Data")
        st.download_button("⬇️ Download Excel", convert_df_excel(filtered_df),
                           "vacancy_details.xlsx", "application/vnd.ms-excel")

    # ---------------------------
    # Page 2: Matching
    # ---------------------------
    elif page == "🤝 Matching":
        st.markdown("## 🤝 Teacher Transfer Matching")

        vac_df = load_vacancy()
        match_type = st.radio("Match Type", ["Reciprocal Matches", "Top-10 Options"], horizontal=True)
        eligibility_filter = st.radio("Eligibility", ["Eligible", "Not Eligible"], horizontal=True)

        # Load Matches
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

        # Teacher Dropdown
        if eligibility_filter == "Eligible":
            teacher_list = vac_df[vac_df["Eligible"] == True][["NIC", "Teacher_Name"]]
        else:
            teacher_list = vac_df[vac_df["Eligible"] == False][["NIC", "Teacher_Name"]]

        teacher_choice = st.selectbox(
            "Select Teacher",
            teacher_list["NIC"] + " - " + teacher_list["Teacher_Name"]
        )
        teacher_nic = teacher_choice.split(" - ")[0]

        # Filter Matches
        matches_for_teacher = df[df[key_col] == teacher_nic]

        if matches_for_teacher.empty:
            st.info("ℹ️ No matches found for this teacher.")
        else:
            st.dataframe(format_eligibility(matches_for_teacher), use_container_width=True)

            # Export
            st.markdown("### 📂 Export Matches")
            st.download_button("⬇️ Download Excel", convert_df_excel(matches_for_teacher),
                               "matches.xlsx", "application/vnd.ms-excel")
