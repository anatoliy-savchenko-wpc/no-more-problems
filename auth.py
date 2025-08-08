"""
Authentication module for user login and permissions
"""
import streamlit as st
from config import load_credentials, load_user_roles

# Load credentials and roles at module level
USER_CREDENTIALS = load_credentials()
USER_ROLES = load_user_roles()

def authenticate_user(username, password):
    """Authenticate user credentials"""
    if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
        return True
    return False

def get_user_role(username):
    """Get user role (Admin, Partner, or User)"""
    # Check if user has explicit role in USER_ROLES
    if username in USER_ROLES:
        return USER_ROLES[username]
    # Default roles based on username
    if username == 'Admin':
        return 'Admin'
    elif 'partner' in username.lower():
        return 'Partner'
    else:
        return 'User'

def logout():
    """Logout current user"""
    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.session_state.user_role = None
    st.session_state.current_file_id = None
    st.session_state.selected_file_for_view = None

def show_login_form():
    """Display login form"""
    st.title("🔐 Login to Problem File Tracker")
    
    with st.form("login_form"):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.selectbox("Select User:", list(USER_CREDENTIALS.keys()) if USER_CREDENTIALS else ["No users available"])
            password = st.text_input("Password:", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                if USER_CREDENTIALS and authenticate_user(username, password):
                    st.session_state.authenticated = True
                    st.session_state.current_user = username
                    st.session_state.user_role = get_user_role(username)
                    st.success(f"Welcome, {username}! (Role: {st.session_state.user_role})")
                    st.rerun()
                else:
                    st.error("Invalid credentials!")