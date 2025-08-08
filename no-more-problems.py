"""
Main application file for Problem File Tracker
"""
import streamlit as st
from datetime import datetime
import uuid

# Import modules
from auth import authenticate_user, get_user_role, show_login_form, logout
from config import initialize_session_state, load_credentials, load_user_roles
from database import load_data, init_supabase
from sidebar import show_sidebar
from pages.dashboard import show_dashboard
from pages.problem_files import (
    show_create_problem_file, 
    show_my_problem_files, 
    show_individual_problem_file
)
from pages.executive_summary import show_executive_summary
from pages.data_management import show_data_management
from utils import can_access_data_management
from email_handler import check_and_send_deadline_alerts

# Configure page
st.set_page_config(
    page_title="Problem File Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide the default Streamlit sidebar pages
st.markdown("""
    <style>
        /* Hide default Streamlit pages in sidebar */
        [data-testid="stSidebarNav"] {
            display: none;
        }
        
        /* Optional: Remove the top padding when nav is hidden */
        [data-testid="stSidebarContent"] {
            padding-top: 2rem;
        }
    </style>
""", unsafe_allow_html=True)

def main():
    """Main application logic"""
    # Initialize session state
    initialize_session_state()
    
    # Load data after authentication
    if st.session_state.authenticated:
        load_data()
        
        # Check for approaching deadlines once per session
        if 'deadline_check_done' not in st.session_state:
            check_and_send_deadline_alerts()
            st.session_state.deadline_check_done = True

    if not st.session_state.authenticated:
        # Clear any existing session data when not authenticated
        if st.session_state.current_user is not None:
            st.session_state.current_user = None
            st.session_state.user_role = None
            st.session_state.current_file_id = None
            st.session_state.selected_file_for_view = None
        
        show_login_form()
    else:
        # Show sidebar
        show_sidebar()
        
        # Route to appropriate page
        if st.session_state.page == "Dashboard":
            show_dashboard()
        
        elif st.session_state.page == "Create Problem File":
            show_create_problem_file()
        
        elif st.session_state.page == "My Problem Files":
            show_my_problem_files()
        
        elif st.session_state.page == "Executive Summary":
            show_executive_summary()
        
        elif st.session_state.page == "Data Management":
            show_data_management()
        
        elif st.session_state.page.startswith("📁 "):
            # Individual problem file view
            if st.session_state.selected_file_for_view:
                show_individual_problem_file(st.session_state.selected_file_for_view)
            else:
                st.error("No file selected!")
                st.session_state.page = "Dashboard"
                st.rerun()
        
        else:
            # Default fallback
            st.session_state.page = "Dashboard"
            st.rerun()

if __name__ == "__main__":
    main()