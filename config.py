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
            'contacts': {},  # Store contacts
            'event_logs': {},  # Store event logs
            'sharepoint_links': {}  # Store SharePoint links
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

# ====== UPDATED UTILITY FUNCTIONS ======

def get_accessible_files():
    """Get all problem files - everyone can see everything"""
    return st.session_state.data.get('problem_files', {})

def calculate_project_progress(tasks):
    """Calculate overall project progress percentage"""
    if not tasks:
        return 0
    
    total_subtasks = 0
    completed_subtasks = 0
    
    for task in tasks.values():
        for subtask in task.get('subtasks', {}).values():
            total_subtasks += 1
            if subtask.get('progress', 0) == 100:
                completed_subtasks += 1
    
    if total_subtasks == 0:
        return 0
    
    return (completed_subtasks / total_subtasks) * 100

def can_edit_file(file_owner):
    """Check if current user can edit a problem file"""
    # Admin and Partners can edit everything
    if st.session_state.user_role in ['Admin', 'Partner']:
        return True
    
    # File owners can edit their own files
    if file_owner == st.session_state.current_user:
        return True
    
    # Check if user is assigned to any subtasks in this file
    # This allows assigned users to edit the file (especially contacts)
    for file_id, file_data in st.session_state.data.get('problem_files', {}).items():
        if file_data.get('owner') == file_owner:
            for task in file_data.get('tasks', {}).values():
                for subtask in task.get('subtasks', {}).values():
                    if subtask.get('assigned_to') == st.session_state.current_user:
                        return True
    
    return False

def can_edit_specific_file(file_id):
    """Check if current user can edit a specific problem file by ID"""
    if file_id not in st.session_state.data.get('problem_files', {}):
        return False
    
    file_data = st.session_state.data['problem_files'][file_id]
    
    # Admin and Partners can edit everything
    if st.session_state.user_role in ['Admin', 'Partner']:
        return True
    
    # File owners can edit their own files
    if file_data.get('owner') == st.session_state.current_user:
        return True
    
    # Check if user is assigned to any subtasks in this specific file
    for task in file_data.get('tasks', {}).values():
        for subtask in task.get('subtasks', {}).values():
            if subtask.get('assigned_to') == st.session_state.current_user:
                return True
    
    return False

def can_delete_items():
    """Check if current user can delete items"""
    return st.session_state.user_role in ['Admin', 'Partner']

def can_add_contacts(file_id):
    """Check if current user can add contacts to a problem file"""
    return can_edit_specific_file(file_id)

def can_edit_contacts(file_id):
    """Check if current user can edit contacts in a problem file"""
    return can_edit_specific_file(file_id)

def can_add_events(file_id):
    """Check if current user can add events to a problem file"""
    return can_edit_specific_file(file_id)

def can_add_sharepoint_links(file_id):
    """Check if current user can add SharePoint links to a problem file"""
    return can_edit_specific_file(file_id)

def check_overdue_and_update(problem_file):
    """Check for overdue tasks and suggest updates"""
    from datetime import datetime, timedelta
    
    overdue_found = False
    today = datetime.now().date()
    
    for task_id, task in problem_file.get('tasks', {}).items():
        for subtask_id, subtask in task.get('subtasks', {}).items():
            if subtask['progress'] < 100:  # Only check incomplete tasks
                end_date = subtask['projected_end_date'].date()
                if end_date < today:
                    overdue_found = True
                    # Could implement auto-update logic here if needed
    
    return overdue_found

def calculate_task_progress(subtasks):
    """Calculate progress for a specific task based on its subtasks"""
    if not subtasks:
        return 0
    
    total_progress = sum(subtask.get('progress', 0) for subtask in subtasks.values())
    return total_progress / len(subtasks)

def get_user_assigned_files():
    """Get files where the current user is assigned to any subtasks"""
    assigned_files = {}
    current_user = st.session_state.current_user
    
    for file_id, file_data in st.session_state.data.get('problem_files', {}).items():
        user_has_assignments = False
        
        for task in file_data.get('tasks', {}).values():
            for subtask in task.get('subtasks', {}).values():
                if subtask.get('assigned_to') == current_user:
                    user_has_assignments = True
                    break
            if user_has_assignments:
                break
        
        if user_has_assignments or file_data.get('owner') == current_user:
            assigned_files[file_id] = file_data
    
    return assigned_files

def is_user_stakeholder(file_id):
    """Check if user is a stakeholder (owner or assigned) in a file"""
    if file_id not in st.session_state.data.get('problem_files', {}):
        return False
    
    file_data = st.session_state.data['problem_files'][file_id]
    current_user = st.session_state.current_user
    
    # Check if user is owner
    if file_data.get('owner') == current_user:
        return True
    
    # Check if user is assigned to any subtasks
    for task in file_data.get('tasks', {}).values():
        for subtask in task.get('subtasks', {}).values():
            if subtask.get('assigned_to') == current_user:
                return True
    
    return False

def get_user_role_display():
    """Get display-friendly user role"""
    role = st.session_state.user_role
    if role == 'Admin':
        return "👑 Administrator"
    elif role == 'Partner':
        return "🤝 Partner"
    else:
        return "👤 User"

def can_assign_files():
    """Check if user can assign files to others"""
    return st.session_state.user_role in ['Admin', 'Partner']

def can_view_all_analytics():
    """Check if user can view analytics for all files"""
    return st.session_state.user_role in ['Admin', 'Partner']