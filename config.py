"""
Configuration and session state management
"""
import streamlit as st

# Load user credentials from TOML file
def load_credentials():
    """Load user credentials from Streamlit secrets"""
    try:
        return st.secrets["credentials"]
    except Exception as e:
        st.error(f"Error loading credentials from secrets: {e}")
        return {}

# Load user roles from TOML file
def load_user_roles():
    """Load user roles from Streamlit secrets"""
    try:
        return st.secrets.get("user_roles", {})
    except Exception as e:
        st.error(f"Error loading user roles from secrets: {e}")
        return {}

# Initialize session state
def initialize_session_state():
    """Initialize all session state variables"""
    if 'data' not in st.session_state:
        # Load credentials at initialization
        USER_CREDENTIALS = load_credentials()
        st.session_state.data = {
            'problem_files': {},
            'users': list(USER_CREDENTIALS.keys()),
            'comments': {},  # Store comments
            'contacts': {}   # Store contacts
        }

    if 'current_file_id' not in st.session_state:
        st.session_state.current_file_id = None

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if 'current_user' not in st.session_state:
        st.session_state.current_user = None

    if 'user_role' not in st.session_state:
        st.session_state.user_role = None

    if 'page' not in st.session_state:
        st.session_state.page = "Dashboard"

    if 'selected_file_for_view' not in st.session_state:
        st.session_state.selected_file_for_view = None