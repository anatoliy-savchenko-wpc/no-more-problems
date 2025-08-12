"""
Sidebar navigation module
"""
import streamlit as st
from auth import logout
from utils import can_access_data_management

def show_sidebar():
    """Display sidebar with navigation"""
    with st.sidebar:
        # Home button
        st.markdown("<div id='home-btn-wrapper'>", unsafe_allow_html=True)
        st.markdown('<span id="button-after"></span>', unsafe_allow_html=True)
        if st.button("**🔧 Problem File Dashboard**", key="home", use_container_width=True):
            st.session_state.page = "Dashboard"
            st.session_state.current_file_id = None
            st.session_state.selected_file_for_view = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

                # Email test section (REMOVE IN PRODUCTION)
        with st.expander("🧪 Test Email System"):
            if st.button("Send Test Email"):
                try:
                    from sendgrid import SendGridAPIClient
                    from sendgrid.helpers.mail import Mail
            
                    # Get your email from secrets
                    test_email = st.secrets["user_emails"].get("Admin", "anatoliy.savchenko@windsorgp.com")
            
                    sg = SendGridAPIClient(st.secrets["sendgrid"]["api_key"])
                    message = Mail(
                        from_email=st.secrets["sendgrid"]["from_email"],
                        to_emails=test_email,
                        subject="Test Email from Problem Tracker",
                        html_content="<h1>Test Email</h1><p>If you see this, SendGrid is working!</p>"
                    )
            
                    response = sg.send(message)
                    st.success(f"✅ Test email sent to {test_email}! Status: {response.status_code}")
            
                except Exception as e:
                    st.error(f"❌ Failed to send test email: {str(e)}")
                    st.write("Error details:", e)

        # CSS for home button
        st.markdown("""
            <style>
                .element-container:has(#button-after) + div button {
                background-color: transparent !important;
                border: none !important;
                color: inherit !important;
                padding: 0 !important;
                text-align: left !important;
                font-size: 1.7rem !important;
                font-weight: 900 !important;
                box-shadow: none !important;
            }
            .element-container:has(#button-after) + button:hover {
                color: #2f74c0 !important;
                background-color: transparent !important;
            }
        </style>""", unsafe_allow_html=True)

        # User info with role badge
        role_badge = {
            'Admin': '👑',
            'Partner': '🤝',
            'User': '👤'
        }.get(st.session_state.user_role, '👤')
        
        st.markdown(f"{role_badge} **Logged in as:** {st.session_state.current_user}")
        st.markdown(f"🔑 **Role:** {st.session_state.user_role}")
        
        if st.button("🚪 Logout"):
            logout()
            st.rerun()
        
        st.markdown("---")
        
        # Navigation menu
        nav_options = ["Dashboard", "Create Problem File", "My Problem Files", "Executive Summary"]
        if can_access_data_management():
            nav_options.append("Data Management")
        
        # Handle individual file views
        if st.session_state.selected_file_for_view:
            file_data = st.session_state.data['problem_files'].get(st.session_state.selected_file_for_view)
            if file_data:
                nav_options.append(f"📁 {file_data['problem_name']}")
        
        page = st.selectbox("Navigate to:", nav_options, 
                           index=nav_options.index(st.session_state.page) if st.session_state.page in nav_options else 0)
        
        # Update session state when page changes
        if page != st.session_state.page:
            st.session_state.page = page
        
        st.markdown("---")
        st.markdown("🔧 **Problem File Tracker v4.0**")
        st.markdown("🗄️ **Database**: Supabase (Persistent)")
        st.markdown("✨ **Features**: Partners, Comments, Contacts")