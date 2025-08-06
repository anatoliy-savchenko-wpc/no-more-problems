import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime, timedelta
import uuid
from typing import Dict, List, Any
import io
import hashlib
import toml
from supabase import create_client, Client

# Configure page
st.set_page_config(
    page_title="Problem File Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

# Load user credentials from TOML file
def load_credentials():
    try:
        return st.secrets["credentials"]
    except Exception as e:
        st.error(f"Error loading credentials from secrets: {e}")
        return {}

# Load credentials at startup
USER_CREDENTIALS = load_credentials()

# Initialize session state
def initialize_session_state():
    if 'data' not in st.session_state:
        st.session_state.data = {
            'problem_files': {},
            'users': list(USER_CREDENTIALS.keys())
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

initialize_session_state()

# Authentication functions
def authenticate_user(username, password):
    """Authenticate user credentials"""
    if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
        return True
    return False

def get_user_role(username):
    """Get user role (Admin or User)"""
    return 'Admin' if username == 'Admin' else 'User'

def logout():
    """Logout current user"""
    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.session_state.user_role = None
    st.session_state.current_file_id = None
    st.session_state.selected_file_for_view = None

def can_access_data_management():
    """Check if user can access data management"""
    return st.session_state.user_role == 'Admin'

def can_delete_items():
    """Check if user can delete items"""
    return st.session_state.user_role == 'Admin'

def can_edit_all_files():
    """Check if user can edit all problem files"""
    return st.session_state.user_role == 'Admin'

def can_edit_file(file_owner):
    """Check if user can edit a specific file"""
    return st.session_state.user_role == 'Admin' or st.session_state.current_user == file_owner

# Login form
def show_login_form():
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
                    st.success(f"Welcome, {username}!")
                    st.rerun()
                else:
                    st.error("Invalid credentials!")

# Supabase data functions
def load_data():
    """Load all data from Supabase into session state"""
    if not st.session_state.authenticated:
        return
        
    try:
        supabase = init_supabase()
        
        # Load problem files with user filtering
        if st.session_state.user_role == 'Admin':
            # Admin sees all files
            problem_files_response = supabase.table('problem_files').select('*').execute()
        else:
            # Regular users see files they own or are assigned to
            # First get files they own
            owned_files = supabase.table('problem_files').select('*').eq('owner', st.session_state.current_user).execute()
            
            # Then get files where they're assigned to subtasks
            assigned_subtasks = supabase.table('subtasks').select('task_id').eq('assigned_to', st.session_state.current_user).execute()
            
            if assigned_subtasks.data:
                task_ids = [subtask['task_id'] for subtask in assigned_subtasks.data]
                assigned_tasks = supabase.table('tasks').select('problem_file_id').in_('id', task_ids).execute()
                
                if assigned_tasks.data:
                    file_ids = [task['problem_file_id'] for task in assigned_tasks.data]
                    assigned_files = supabase.table('problem_files').select('*').in_('id', file_ids).execute()
                else:
                    assigned_files = type('obj', (object,), {'data': []})
            else:
                assigned_files = type('obj', (object,), {'data': []})
            
            # Combine results
            all_file_ids = set()
            problem_files_data = []
            
            for pf in owned_files.data:
                if pf['id'] not in all_file_ids:
                    problem_files_data.append(pf)
                    all_file_ids.add(pf['id'])
                    
            for pf in assigned_files.data:
                if pf['id'] not in all_file_ids:
                    problem_files_data.append(pf)
                    all_file_ids.add(pf['id'])
                    
            problem_files_response = type('obj', (object,), {'data': problem_files_data})
        
        problem_files = {}
        
        for pf in problem_files_response.data:
            file_id = pf['id']
            
            # Parse dates safely
            def safe_parse_date(date_str):
                if isinstance(date_str, str):
                    # Handle different datetime formats
                    date_str = date_str.replace('Z', '+00:00')
                    if '+00:00' not in date_str and 'T' in date_str:
                        date_str += '+00:00'
                    return datetime.fromisoformat(date_str)
                return date_str if isinstance(date_str, datetime) else datetime.now()
            
            problem_files[file_id] = {
                'problem_name': pf['problem_name'],
                'owner': pf['owner'],
                'project_start_date': safe_parse_date(pf['project_start_date']),
                'display_week': pf['display_week'],
                'created_date': safe_parse_date(pf['created_date']),
                'last_modified': safe_parse_date(pf['last_modified']),
                'tasks': {}
            }
            
            # Load tasks for this problem file
            tasks_response = supabase.table('tasks').select('*').eq('problem_file_id', file_id).execute()
            
            for task in tasks_response.data:
                task_id = task['id']
                problem_files[file_id]['tasks'][task_id] = {
                    'name': task['name'],
                    'description': task['description'] or '',
                    'subtasks': {}
                }
                
                # Load subtasks for this task
                subtasks_response = supabase.table('subtasks').select('*').eq('task_id', task_id).execute()
                
                for subtask in subtasks_response.data:
                    subtask_id = subtask['id']
                    problem_files[file_id]['tasks'][task_id]['subtasks'][subtask_id] = {
                        'name': subtask['name'],
                        'assigned_to': subtask['assigned_to'],
                        'start_date': safe_parse_date(subtask['start_date']),
                        'projected_end_date': safe_parse_date(subtask['projected_end_date']),
                        'progress': subtask['progress'],
                        'notes': subtask['notes'] or ''
                    }
        
        st.session_state.data['problem_files'] = problem_files
        
    except Exception as e:
        st.error(f"Error loading data from Supabase: {e}")
        # Initialize empty data structure on error
        st.session_state.data['problem_files'] = {}

def save_problem_file(file_id: str, file_data: dict):
    """Save or update a problem file"""
    try:
        supabase = init_supabase()
        
        db_data = {
            'id': file_id,
            'problem_name': file_data['problem_name'],
            'owner': file_data['owner'],
            'project_start_date': file_data['project_start_date'].isoformat(),
            'display_week': file_data['display_week']
        }
        
        # Use upsert to handle both insert and update
        supabase.table('problem_files').upsert(db_data).execute()
        return True
        
    except Exception as e:
        st.error(f"Error saving problem file: {e}")
        return False

def save_task(problem_file_id: str, task_id: str, task_data: dict):
    """Save or update a task"""
    try:
        supabase = init_supabase()
        
        db_data = {
            'id': task_id,
            'problem_file_id': problem_file_id,
            'name': task_data['name'],
            'description': task_data.get('description', '')
        }
        
        supabase.table('tasks').upsert(db_data).execute()
        return True
        
    except Exception as e:
        st.error(f"Error saving task: {e}")
        return False

def save_subtask(task_id: str, subtask_id: str, subtask_data: dict):
    """Save or update a subtask"""
    try:
        supabase = init_supabase()
        
        db_data = {
            'id': subtask_id,
            'task_id': task_id,
            'name': subtask_data['name'],
            'assigned_to': subtask_data['assigned_to'],
            'start_date': subtask_data['start_date'].isoformat(),
            'projected_end_date': subtask_data['projected_end_date'].isoformat(),
            'progress': subtask_data['progress'],
            'notes': subtask_data.get('notes', '')
        }
        
        supabase.table('subtasks').upsert(db_data).execute()
        return True
        
    except Exception as e:
        st.error(f"Error saving subtask: {e}")
        return False

def delete_problem_file(file_id: str):
    """Delete a problem file and all related data"""
    try:
        supabase = init_supabase()
        supabase.table('problem_files').delete().eq('id', file_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting problem file: {e}")
        return False

def delete_task(task_id: str):
    """Delete a task and all its subtasks"""
    try:
        supabase = init_supabase()
        supabase.table('tasks').delete().eq('id', task_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting task: {e}")
        return False

def delete_subtask(subtask_id: str):
    """Delete a subtask"""
    try:
        supabase = init_supabase()
        supabase.table('subtasks').delete().eq('id', subtask_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting subtask: {e}")
        return False

# Helper function to calculate task progress
def calculate_task_progress(subtasks):
    if not subtasks:
        return 0
    total_progress = sum(subtask['progress'] for subtask in subtasks.values())
    return total_progress / len(subtasks)

# Helper function to calculate overall project progress
def calculate_project_progress(tasks):
    if not tasks:
        return 0
    task_progresses = []
    for task in tasks.values():
        if task['subtasks']:
            task_progress = calculate_task_progress(task['subtasks'])
        else:
            task_progress = 0
        task_progresses.append(task_progress)
    return sum(task_progresses) / len(task_progresses) if task_progresses else 0

# Helper function to check for overdue tasks
def check_overdue_and_update(problem_file):
    today = datetime.now().date()
    updated = False
    
    for task_id, task in problem_file['tasks'].items():
        for subtask_id, subtask in task['subtasks'].items():
            if (subtask['projected_end_date'].date() < today and 
                subtask['progress'] < 100):
                # Push forward by 1 week
                subtask['projected_end_date'] += timedelta(weeks=1)
                subtask['notes'] += f"\n[AUTO-UPDATE {datetime.now().strftime('%Y-%m-%d')}]: Deadline pushed forward due to overdue status."
                
                # Save the updated subtask to database
                save_subtask(task_id, subtask_id, subtask)
                updated = True
    
    return updated

# Create Gantt chart
def create_gantt_chart(problem_file):
    tasks_data = []
    
    for task_id, task in problem_file['tasks'].items():
        for subtask_id, subtask in task['subtasks'].items():
            # Determine color based on progress
            if subtask['progress'] == 100:
                color = 'green'
            elif subtask['progress'] > 0:
                color = 'orange'
            else:
                color = 'red'
            
            # Check if overdue
            is_overdue = (subtask['projected_end_date'].date() < datetime.now().date() and 
                         subtask['progress'] < 100)
            
            tasks_data.append({
                'Task': f"{task['name']} - {subtask['name']}",
                'Start': subtask['start_date'],
                'Finish': subtask['projected_end_date'],
                'Progress': subtask['progress'],
                'Assigned To': subtask['assigned_to'],
                'Color': color,
                'Overdue': is_overdue
            })
    
    if not tasks_data:
        return None
    
    df = pd.DataFrame(tasks_data)
    
    fig = px.timeline(
        df, 
        x_start="Start", 
        x_end="Finish", 
        y="Task",
        color='Color',
        hover_data=['Progress', 'Assigned To', 'Overdue'],
        title=f"Gantt Chart - {problem_file['problem_name']}"
    )
    
    fig.update_layout(
        height=max(400, len(tasks_data) * 30),
        xaxis_title="Timeline",
        yaxis_title="Tasks"
    )
    
    return fig

# Filter files based on user permissions
def get_accessible_files():
    """Get files accessible to current user"""
    if not st.session_state.authenticated:
        return {}
    
    if st.session_state.user_role == 'Admin':
        return st.session_state.data['problem_files']
    else:
        # Regular users can only see files they own or are assigned to
        accessible_files = {}
        for file_id, file_data in st.session_state.data['problem_files'].items():
            if file_data['owner'] == st.session_state.current_user:
                accessible_files[file_id] = file_data
            else:
                # Check if user is assigned to any tasks in this file
                for task_id, task in file_data['tasks'].items():
                    for subtask_id, subtask in task['subtasks'].items():
                        if subtask['assigned_to'] == st.session_state.current_user:
                            accessible_files[file_id] = file_data
                            break
        return accessible_files

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

        # User info
        st.markdown(f"👤 **Logged in as:** {st.session_state.current_user}")
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
        st.markdown("🔧 **Problem File Tracker v3.1**")
        st.markdown("🗄️ **Database**: Supabase (Persistent)")

def show_dashboard():
    """Display main dashboard"""
    st.title("📊 Problem File Tracker Dashboard")
    
    accessible_files = get_accessible_files()
    
    if not accessible_files:
        st.info("No problem files available. Create a new one or ask an admin for access!")
        if st.button("➕ Create Your First Problem File", use_container_width=True):
            st.session_state.page = "Create Problem File"
            st.rerun()
    else:
        st.subheader("Available Problem Files")
        
        # Display problem files in a grid
        cols = st.columns(3)
        for i, (file_id, file_data) in enumerate(accessible_files.items()):
            with cols[i % 3]:
                progress = calculate_project_progress(file_data['tasks'])
                
                # Show ownership indicator
                ownership_indicator = "👑 Owner" if file_data['owner'] == st.session_state.current_user else f"👤 Owner: {file_data['owner']}"
                
                st.metric(
                    label=file_data['problem_name'],
                    value=f"{progress:.1f}%",
                    delta=ownership_indicator
                )
                
                if st.button(f"Open {file_data['problem_name']}", key=f"open_{file_id}"):
                    st.session_state.selected_file_for_view = file_id
                    st.session_state.page = f"📁 {file_data['problem_name']}"
                    st.rerun()
        
        # Quick actions
        st.subheader("Quick Actions")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("➕ Create New Problem File", use_container_width=True):
                st.session_state.page = "Create Problem File"
                st.rerun()
        with col2:
            if st.button("📁 View All My Files", use_container_width=True):
                st.session_state.page = "My Problem Files"
                st.rerun()
        with col3:
            if st.button("📊 Executive Summary", use_container_width=True):
                st.session_state.page = "Executive Summary"
                st.rerun()
        
        # Recent Notes Section
        show_recent_notes(accessible_files)

def show_recent_notes(accessible_files):
    """Display recent notes section"""
    st.subheader("📝 Recent Notes & Comments")
    
    all_notes = []
    for file_id, file_data in accessible_files.items():
        for task_id, task in file_data['tasks'].items():
            for subtask_id, subtask in task['subtasks'].items():
                if subtask.get('notes', '').strip():
                    # Only show notes for tasks assigned to user or if user is admin/owner
                    if (st.session_state.user_role == 'Admin' or 
                        file_data['owner'] == st.session_state.current_user or 
                        subtask['assigned_to'] == st.session_state.current_user):
                        all_notes.append({
                            'Project': file_data['problem_name'],
                            'Task': f"{task['name']} - {subtask['name']}",
                            'Assigned To': subtask['assigned_to'],
                            'Progress': f"{subtask['progress']}%",
                            'Notes': subtask['notes'],
                            'Due Date': subtask['projected_end_date'].strftime('%Y-%m-%d'),
                            'Status': '🔴 Overdue' if (subtask['projected_end_date'].date() < datetime.now().date() and subtask['progress'] < 100) else '🟢 On Track'
                        })
    
    if all_notes:
        # Filter options
        col1, col2, col3 = st.columns(3)
        with col1:
            project_filter = st.selectbox("Filter by Project:", 
                                        ["All Projects"] + list(set([note['Project'] for note in all_notes])))
        with col2:
            assignee_filter = st.selectbox("Filter by Assignee:", 
                                         ["All Assignees"] + list(set([note['Assigned To'] for note in all_notes])))
        with col3:
            status_filter = st.selectbox("Filter by Status:", 
                                       ["All Status", "🟢 On Track", "🔴 Overdue"])
        
        # Apply filters
        df_notes = pd.DataFrame(all_notes)
        filtered_notes = df_notes.copy()
        if project_filter != "All Projects":
            filtered_notes = filtered_notes[filtered_notes['Project'] == project_filter]
        if assignee_filter != "All Assignees":
            filtered_notes = filtered_notes[filtered_notes['Assigned To'] == assignee_filter]
        if status_filter != "All Status":
            filtered_notes = filtered_notes[filtered_notes['Status'] == status_filter]
        
        # Display filtered notes
        if not filtered_notes.empty:
            st.dataframe(filtered_notes, use_container_width=True, height=400)
        else:
            st.info("No notes match the selected filters.")
    else:
        st.info("No notes or comments found. Add some notes to your tasks to see them here!")

def show_create_problem_file():
    """Display create problem file page"""
    st.title("➕ Create New Problem File")
    
    with st.form("new_problem_file"):
        col1, col2 = st.columns(2)
        with col1:
            problem_name = st.text_input("Problem Name*")
            # Only admin can assign to any user, others default to themselves
            if st.session_state.user_role == 'Admin':
                owner = st.selectbox("Owner*", st.session_state.data['users'])
            else:
                owner = st.session_state.current_user
                st.write(f"**Owner:** {owner}")
        with col2:
            project_start_date = st.date_input("Project Start Date*", datetime.now())
            display_week = st.number_input("Display Week", min_value=1, value=1)
        
        description = st.text_area("Problem Description (Optional)")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Create Problem File", use_container_width=True):
                if problem_name:
                    file_id = str(uuid.uuid4())
                    file_data = {
                        'problem_name': problem_name,
                        'owner': owner,
                        'project_start_date': datetime.combine(project_start_date, datetime.min.time()),
                        'display_week': display_week,
                        'tasks': {},
                        'created_date': datetime.now(),
                        'last_modified': datetime.now()
                    }
                    
                    if save_problem_file(file_id, file_data):
                        st.session_state.data['problem_files'][file_id] = file_data
                        st.success(f"Problem file '{problem_name}' created successfully!")
                        
                        # Auto-navigate to the new file
                        st.session_state.selected_file_for_view = file_id
                        st.session_state.page = f"📁 {problem_name}"
                        st.rerun()
                    else:
                        st.error("Failed to create problem file.")
                else:
                    st.error("Please fill in all required fields.")
        
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.page = "Dashboard"
                st.rerun()

def show_my_problem_files():
    """Display user's problem files management page"""
    st.title("📁 My Problem Files")
    
    accessible_files = get_accessible_files()
    
    if not accessible_files:
        st.info("No problem files available.")
        if st.button("➕ Create Your First Problem File"):
            st.session_state.page = "Create Problem File"
            st.rerun()
        return
    
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Files", len(accessible_files))
    with col2:
        owned_files = len([f for f in accessible_files.values() if f['owner'] == st.session_state.current_user])
        st.metric("Files I Own", owned_files)
    with col3:
        assigned_files = len(accessible_files) - owned_files
        st.metric("Files Assigned To Me", assigned_files)
    with col4:
        completed = len([f for f in accessible_files.values() if calculate_project_progress(f['tasks']) >= 100])
        st.metric("Completed", completed)
    
    # Files table with actions
    st.subheader("Problem Files")
    
    files_data = []
    for file_id, file_data in accessible_files.items():
        progress = calculate_project_progress(file_data['tasks'])
        files_data.append({
            'ID': file_id,
            'Name': file_data['problem_name'],
            'Owner': file_data['owner'],
            'Progress': f"{progress:.1f}%",
            'Created': file_data.get('created_date', datetime.now()).strftime('%Y-%m-%d'),
            'Last Modified': file_data.get('last_modified', datetime.now()).strftime('%Y-%m-%d %H:%M')
        })
    
    if files_data:
        df_files = pd.DataFrame(files_data)
        st.dataframe(df_files.drop('ID', axis=1), use_container_width=True)

        # Manual selection dropdown
        file_selector = {
            f"{file['Name']} (Owner: {file['Owner']})": file["ID"]
            for file in files_data
        }

        selected_label = st.selectbox("Select a file to manage:", list(file_selector.keys()))
        selected_file_id = file_selector[selected_label]
        selected_file_data = accessible_files[selected_file_id]

        # Action buttons
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("📂 Open File", use_container_width=True):
                st.session_state.selected_file_for_view = selected_file_id
                st.session_state.page = f"📁 {selected_file_data['problem_name']}"
                st.rerun()

        with col2:
            if st.button("📊 View Summary", use_container_width=True):
                st.session_state.page = "Executive Summary"
                st.rerun()

        with col3:
            if can_edit_file(selected_file_data['owner']):
                if st.button("✏️ Edit", use_container_width=True):
                    st.session_state.selected_file_for_view = selected_file_id
                    st.session_state.page = f"📁 {selected_file_data['problem_name']}"
                    st.rerun()
            else:
                st.write("👁️ View Only")

        with col4:
            if can_delete_items():
                if st.button("🗑️ Delete File", use_container_width=True, type="secondary"):
                    st.session_state.file_to_delete = selected_file_id
                    st.rerun()

        
        # Handle file deletion confirmation
        if hasattr(st.session_state, 'file_to_delete') and st.session_state.file_to_delete:
            file_to_delete = st.session_state.file_to_delete
            file_name = accessible_files[file_to_delete]['problem_name']
            
            st.error(f"⚠️ **Confirm Deletion of '{file_name}'**")
            st.warning("This action cannot be undone. All tasks and subtasks will be permanently deleted.")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, Delete Permanently", type="primary", use_container_width=True):
                    if delete_problem_file(file_to_delete):
                        del st.session_state.data['problem_files'][file_to_delete]
                        st.success(f"Problem file '{file_name}' deleted successfully!")
                        if hasattr(st.session_state, 'file_to_delete'):
                            delattr(st.session_state, 'file_to_delete')
                        st.rerun()
                    else:
                        st.error("Failed to delete problem file.")
            
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    if hasattr(st.session_state, 'file_to_delete'):
                        delattr(st.session_state, 'file_to_delete')
                    st.rerun()

def show_individual_problem_file(file_id):
    """Display individual problem file management page"""
    if file_id not in st.session_state.data['problem_files']:
        st.error("Problem file not found!")
        return
    
    problem_file = st.session_state.data['problem_files'][file_id]
    
    # Page header
    st.title(f"📁 {problem_file['problem_name']}")
    
    # Quick info bar
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Owner", problem_file['owner'])
    with col2:
        progress = calculate_project_progress(problem_file['tasks'])
        st.metric("Progress", f"{progress:.1f}%")
    with col3:
        st.metric("Total Tasks", len(problem_file['tasks']))
    with col4:
        total_subtasks = sum(len(task['subtasks']) for task in problem_file['tasks'].values())
        st.metric("Total Subtasks", total_subtasks)
    
    # Check permissions
    can_edit = can_edit_file(problem_file['owner'])
    
    if not can_edit:
        st.info("👁️ **View Only Mode** - You can view this file but cannot make changes. Contact the owner for edit access.")
    
    # Check for overdue tasks and update (only if can edit)
    if can_edit and check_overdue_and_update(problem_file):
        st.warning("Some overdue tasks have been automatically updated with new deadlines.")
    
    # Navigation tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Tasks & Subtasks", "📊 Gantt Chart", "📝 File Settings", "📈 Analytics"])
    
    with tab1:
        show_task_management(file_id, problem_file, can_edit)
    
    with tab2:
        show_gantt_chart_tab(problem_file)
    
    with tab3:
        show_file_settings(file_id, problem_file, can_edit)
    
    with tab4:
        show_file_analytics(problem_file)

def show_task_management(file_id, problem_file, can_edit):
    """Display task management interface"""
    
    # Add new main task (only if can edit)
    if can_edit:
        with st.expander("➕ Add New Main Task"):
            with st.form("new_main_task"):
                task_name = st.text_input("Main Task Name*")
                task_description = st.text_area("Task Description")
                
                if st.form_submit_button("Add Main Task"):
                    if task_name:
                        task_id = str(uuid.uuid4())
                        task_data = {
                            'name': task_name,
                            'description': task_description,
                            'subtasks': {}
                        }
                        
                        if save_task(file_id, task_id, task_data):
                            problem_file['tasks'][task_id] = task_data
                            st.success(f"Main task '{task_name}' added!")
                            st.rerun()
                        else:
                            st.error("Failed to add task.")
    
    # Display existing tasks
    if not problem_file['tasks']:
        st.info("No tasks yet. Add your first task above!")
        return
    
    for task_id, task in problem_file['tasks'].items():
        with st.expander(f"📂 {task['name']}", expanded=True):
            
            # Task header with progress and delete option
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**Description:** {task.get('description', 'No description')}")
                task_progress = calculate_task_progress(task['subtasks'])
                st.progress(task_progress / 100, text=f"Task Progress: {task_progress:.1f}%")
            with col2:
                if can_edit and can_delete_items():
                    if st.button("🗑️ Delete Task", key=f"delete_task_{task_id}"):
                        if delete_task(task_id):
                            del problem_file['tasks'][task_id]
                            st.success("Task deleted!")
                            st.rerun()
            
            # Add subtask form (only if can edit)
            if can_edit:
                show_add_subtask_form(task_id, task, file_id)
            
            # Display existing subtasks
            if task['subtasks']:
                show_subtasks_table(task_id, task, problem_file, can_edit)
            else:
                st.info("No subtasks yet. Add subtasks to start tracking progress!")

def show_add_subtask_form(task_id, task, file_id):
    """Display add subtask form"""
    with st.form(f"add_subtask_{task_id}"):
        st.write("**Add New Subtask:**")
        subcol1, subcol2, subcol3 = st.columns(3)
        with subcol1:
            subtask_name = st.text_input("Subtask Name*", key=f"subtask_name_{task_id}")
            assigned_to = st.selectbox("Assigned To*", st.session_state.data['users'], 
                                     key=f"assigned_{task_id}")
        with subcol2:
            start_date = st.date_input("Start Date*", datetime.now(), key=f"start_{task_id}")
            progress = st.slider("Progress %", 0, 100, 0, key=f"progress_{task_id}")
        with subcol3:
            end_date = st.date_input("Projected End Date*", 
                                   datetime.now() + timedelta(weeks=1), 
                                   key=f"end_{task_id}")
            notes = st.text_area("Notes", key=f"notes_{task_id}")
        
        if st.form_submit_button("Add Subtask"):
            if subtask_name and assigned_to:
                subtask_id = str(uuid.uuid4())
                subtask_data = {
                    'name': subtask_name,
                    'assigned_to': assigned_to,
                    'start_date': datetime.combine(start_date, datetime.min.time()),
                    'projected_end_date': datetime.combine(end_date, datetime.min.time()),
                    'progress': progress,
                    'notes': notes
                }
                
                if save_subtask(task_id, subtask_id, subtask_data):
                    task['subtasks'][subtask_id] = subtask_data
                    st.success(f"Subtask '{subtask_name}' added!")
                    st.rerun()
                else:
                    st.error("Failed to add subtask.")
            else:
                st.error("Please fill in required fields.")

def show_subtasks_table(task_id, task, problem_file, can_edit):
    """Display subtasks table with edit capabilities"""
    st.write("**Existing Subtasks:**")
    
    subtask_data = []
    for subtask_id, subtask in task['subtasks'].items():
        is_overdue = (subtask['projected_end_date'].date() < datetime.now().date() and 
                    subtask['progress'] < 100)
        subtask_data.append({
            'ID': subtask_id,
            'Name': subtask['name'],
            'Assigned To': subtask['assigned_to'],
            'Progress': f"{subtask['progress']}%",
            'Start Date': subtask['start_date'].strftime('%Y-%m-%d'),
            'End Date': subtask['projected_end_date'].strftime('%Y-%m-%d'),
            'Status': '🔴 Overdue' if is_overdue else '🟢 On Track',
            'Notes': subtask['notes'][:50] + '...' if len(subtask['notes']) > 50 else subtask['notes']
        })
    
    df_subtasks = pd.DataFrame(subtask_data)
    st.dataframe(df_subtasks.drop('ID', axis=1), use_container_width=True)
    
    # Edit subtask section (only if can edit)
    if can_edit:
        subtask_to_edit = st.selectbox(
            f"Select subtask to edit:",
            options=[None] + list(task['subtasks'].keys()),
            format_func=lambda x: "Select..." if x is None else task['subtasks'][x]['name'],
            key=f"edit_select_{task_id}"
        )
        
        if subtask_to_edit:
            show_edit_subtask_form(task_id, subtask_to_edit, task, problem_file)

def show_edit_subtask_form(task_id, subtask_id, task, problem_file):
    """Display edit subtask form"""
    subtask = task['subtasks'][subtask_id]
    
    # Check if user can edit this specific subtask
    can_edit_subtask = (st.session_state.user_role == 'Admin' or 
                       problem_file['owner'] == st.session_state.current_user or
                       subtask['assigned_to'] == st.session_state.current_user)
    
    if not can_edit_subtask:
        st.info("You can only edit subtasks assigned to you.")
        return
    
    with st.form(f"edit_subtask_{task_id}_{subtask_id}"):
        st.write(f"**Editing: {subtask['name']}**")
        ecol1, ecol2, ecol3 = st.columns(3)
        with ecol1:
            new_subtask_name = st.text_input("Subtask Name", value=subtask['name'], key=f"edit_name_{task_id}_{subtask_id}")
            # Only admin and owner can reassign tasks
            if st.session_state.user_role == 'Admin' or problem_file['owner'] == st.session_state.current_user:
                new_assigned_to = st.selectbox("Assigned To", st.session_state.data['users'],
                                             index=st.session_state.data['users'].index(subtask['assigned_to']),
                                             key=f"edit_assigned_{task_id}_{subtask_id}")
            else:
                new_assigned_to = subtask['assigned_to']
                st.write(f"**Assigned To:** {new_assigned_to}")
        with ecol2:
            new_start_date = st.date_input("Start Date", value=subtask['start_date'].date(), key=f"edit_start_{task_id}_{subtask_id}")
            new_progress = st.slider("Progress %", 0, 100, subtask['progress'], key=f"edit_progress_{task_id}_{subtask_id}")
        with ecol3:
            new_end_date = st.date_input("Projected End Date", 
                                       value=subtask['projected_end_date'].date(),
                                       key=f"edit_end_{task_id}_{subtask_id}")
            new_notes = st.text_area("Notes", value=subtask['notes'], key=f"edit_notes_{task_id}_{subtask_id}")
        
        col_update, col_delete = st.columns(2)
        with col_update:
            if st.form_submit_button("Update Subtask"):
                subtask['name'] = new_subtask_name
                subtask['assigned_to'] = new_assigned_to
                subtask['start_date'] = datetime.combine(new_start_date, datetime.min.time())
                subtask['projected_end_date'] = datetime.combine(new_end_date, datetime.min.time())
                subtask['progress'] = new_progress
                subtask['notes'] = new_notes
                
                if save_subtask(task_id, subtask_id, subtask):
                    problem_file['last_modified'] = datetime.now()
                    st.success("Subtask updated!")
                    st.rerun()
                else:
                    st.error("Failed to update subtask.")
        
        with col_delete:
            if can_delete_items():
                if st.form_submit_button("Delete Subtask", type="secondary"):
                    if delete_subtask(subtask_id):
                        del task['subtasks'][subtask_id]
                        problem_file['last_modified'] = datetime.now()
                        st.success("Subtask deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete subtask.")

def show_gantt_chart_tab(problem_file):
    """Display Gantt chart tab"""
    st.subheader("📈 Project Timeline")
    
    gantt_fig = create_gantt_chart(problem_file)
    if gantt_fig:
        st.plotly_chart(gantt_fig, use_container_width=True)
        
        # Timeline insights
        st.subheader("📊 Timeline Insights")
        
        # Calculate project duration and other metrics
        all_dates = []
        overdue_count = 0
        completed_count = 0
        
        for task in problem_file['tasks'].values():
            for subtask in task['subtasks'].values():
                all_dates.extend([subtask['start_date'], subtask['projected_end_date']])
                if subtask['progress'] == 100:
                    completed_count += 1
                elif subtask['projected_end_date'].date() < datetime.now().date() and subtask['progress'] < 100:
                    overdue_count += 1
        
        if all_dates:
            project_start = min(all_dates)
            project_end = max(all_dates)
            duration_days = (project_end - project_start).days
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Project Duration", f"{duration_days} days")
            with col2:
                st.metric("Completed Subtasks", completed_count)
            with col3:
                st.metric("Overdue Subtasks", overdue_count)
            with col4:
                st.metric("Project End Date", project_end.strftime('%Y-%m-%d'))
    else:
        st.info("No tasks to display in Gantt chart. Add some subtasks first!")

def show_file_settings(file_id, problem_file, can_edit):
    """Display file settings tab"""
    st.subheader("⚙️ File Settings")
    
    if can_edit:
        with st.form("edit_metadata"):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("Problem Name", value=problem_file['problem_name'])
                # Only admin can change owner
                if st.session_state.user_role == 'Admin':
                    new_owner = st.selectbox("Owner", st.session_state.data['users'], 
                                            index=st.session_state.data['users'].index(problem_file['owner']))
                else:
                    new_owner = problem_file['owner']
                    st.write(f"**Owner:** {new_owner}")
            with col2:
                new_start_date = st.date_input("Project Start Date", 
                                             value=problem_file['project_start_date'].date())
                new_display_week = st.number_input("Display Week", 
                                                 value=problem_file['display_week'], min_value=1)
            
            if st.form_submit_button("Update Settings"):
                problem_file['problem_name'] = new_name
                problem_file['owner'] = new_owner
                problem_file['project_start_date'] = datetime.combine(new_start_date, datetime.min.time())
                problem_file['display_week'] = new_display_week
                problem_file['last_modified'] = datetime.now()
                
                if save_problem_file(file_id, problem_file):
                    st.success("Settings updated successfully!")
                    # Update the page title in session state
                    st.session_state.page = f"📁 {new_name}"
                    st.rerun()
                else:
                    st.error("Failed to update settings.")
    else:
        # Display read-only information
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Problem Name:** {problem_file['problem_name']}")
            st.write(f"**Owner:** {problem_file['owner']}")
        with col2:
            st.write(f"**Project Start Date:** {problem_file['project_start_date'].strftime('%Y-%m-%d')}")
            st.write(f"**Display Week:** {problem_file['display_week']}")
    
    # File information (always visible)
    st.subheader("📋 File Information")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Created:** {problem_file.get('created_date', 'Unknown').strftime('%Y-%m-%d %H:%M') if hasattr(problem_file.get('created_date'), 'strftime') else 'Unknown'}")
        st.write(f"**Total Tasks:** {len(problem_file['tasks'])}")
    with col2:
        st.write(f"**Last Modified:** {problem_file.get('last_modified', 'Unknown').strftime('%Y-%m-%d %H:%M') if hasattr(problem_file.get('last_modified'), 'strftime') else 'Unknown'}")
        total_subtasks = sum(len(task['subtasks']) for task in problem_file['tasks'].values())
        st.write(f"**Total Subtasks:** {total_subtasks}")

def show_file_analytics(problem_file):
    """Display file analytics tab"""
    st.subheader("📊 Project Analytics")
    
    if not problem_file['tasks']:
        st.info("No tasks available for analytics.")
        return
    
    # Collect analytics data
    user_workload = {}
    progress_data = []
    status_data = {'Completed': 0, 'In Progress': 0, 'Not Started': 0, 'Overdue': 0}
    
    for task in problem_file['tasks'].values():
        for subtask in task['subtasks'].values():
            # User workload
            user = subtask['assigned_to']
            if user not in user_workload:
                user_workload[user] = {'total': 0, 'completed': 0, 'overdue': 0}
            user_workload[user]['total'] += 1
            
            # Progress tracking
            progress_data.append(subtask['progress'])
            
            # Status tracking
            if subtask['progress'] == 100:
                status_data['Completed'] += 1
                user_workload[user]['completed'] += 1
            elif subtask['progress'] > 0:
                status_data['In Progress'] += 1
            else:
                status_data['Not Started'] += 1
            
            # Check if overdue
            if (subtask['projected_end_date'].date() < datetime.now().date() and 
                subtask['progress'] < 100):
                status_data['Overdue'] += 1
                user_workload[user]['overdue'] += 1
    
    # Display charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Progress distribution
        if progress_data:
            fig_progress = px.histogram(
                x=progress_data,
                nbins=10,
                title="Progress Distribution",
                labels={'x': 'Progress (%)', 'y': 'Number of Subtasks'}
            )
            st.plotly_chart(fig_progress, use_container_width=True)
    
    with col2:
        # Status pie chart
        fig_status = px.pie(
            values=list(status_data.values()),
            names=list(status_data.keys()),
            title="Task Status Distribution"
        )
        st.plotly_chart(fig_status, use_container_width=True)
    
    # User workload analysis
    if user_workload:
        st.subheader("👥 Team Workload Analysis")
        
        workload_data = []
        for user, data in user_workload.items():
            completion_rate = (data['completed'] / data['total'] * 100) if data['total'] > 0 else 0
            workload_data.append({
                'User': user,
                'Total Tasks': data['total'],
                'Completed': data['completed'],
                'Overdue': data['overdue'],
                'Completion Rate': f"{completion_rate:.1f}%"
            })
        
        df_workload = pd.DataFrame(workload_data)
        st.dataframe(df_workload, use_container_width=True)

def show_executive_summary():
    """Display executive summary page"""
    st.title("📊 Executive Summary")
    
    accessible_files = get_accessible_files()
    
    if not accessible_files:
        st.info("No problem files to summarize.")
        return
    
    # Summary metrics
    total_files = len(accessible_files)
    overdue_count = 0
    completed_count = 0
    
    summary_data = []
    
    for file_id, file_data in accessible_files.items():
        progress = calculate_project_progress(file_data['tasks'])
        
        # Count overdue tasks
        overdue_tasks = []
        for task_id, task in file_data['tasks'].items():
            for subtask_id, subtask in task['subtasks'].items():
                if (subtask['projected_end_date'].date() < datetime.now().date() and 
                    subtask['progress'] < 100):
                    overdue_tasks.append(f"{task['name']} - {subtask['name']}")
        
        if overdue_tasks:
            overdue_count += 1
        
        if progress >= 100:
            completed_count += 1
        
        summary_data.append({
            'Problem File': file_data['problem_name'],
            'Owner': file_data['owner'],
            'Progress': f"{progress:.1f}%",
            'Overdue Tasks': len(overdue_tasks),
            'Status': '✅ Complete' if progress >= 100 else '🔴 Overdue' if overdue_tasks else '🟡 In Progress',
            'Last Modified': file_data.get('last_modified', datetime.now()).strftime('%Y-%m-%d %H:%M') if hasattr(file_data.get('last_modified', datetime.now()), 'strftime') else str(file_data.get('last_modified', 'N/A'))
        })
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Accessible Projects", total_files)
    with col2:
        st.metric("Completed", completed_count)
    with col3:
        st.metric("With Overdue Tasks", overdue_count)
    with col4:
        st.metric("On Track", total_files - overdue_count - completed_count)
    
    # Summary table
    st.subheader("Project Overview")
    df_summary = pd.DataFrame(summary_data)
    st.dataframe(df_summary, use_container_width=True)
    
    # Progress chart
    st.subheader("Progress Distribution")
    progress_values = [float(row['Progress'].replace('%', '')) for row in summary_data]
    
    fig = px.histogram(
        x=progress_values,
        nbins=10,
        title="Project Progress Distribution",
        labels={'x': 'Progress (%)', 'y': 'Number of Projects'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed overdue tasks
    st.subheader("🚨 Overdue Tasks Details")
    overdue_details = []
    
    for file_id, file_data in accessible_files.items():
        for task_id, task in file_data['tasks'].items():
            for subtask_id, subtask in task['subtasks'].items():
                if (subtask['projected_end_date'].date() < datetime.now().date() and 
                    subtask['progress'] < 100):
                    # Only show if user has access to this task
                    if (st.session_state.user_role == 'Admin' or 
                        file_data['owner'] == st.session_state.current_user or 
                        subtask['assigned_to'] == st.session_state.current_user):
                        days_overdue = (datetime.now().date() - subtask['projected_end_date'].date()).days
                        overdue_details.append({
                            'Project': file_data['problem_name'],
                            'Task': f"{task['name']} - {subtask['name']}",
                            'Assigned To': subtask['assigned_to'],
                            'Days Overdue': days_overdue,
                            'Progress': f"{subtask['progress']}%",
                            'Original Due Date': subtask['projected_end_date'].strftime('%Y-%m-%d')
                        })
    
    if overdue_details:
        df_overdue = pd.DataFrame(overdue_details)
        df_overdue = df_overdue.sort_values('Days Overdue', ascending=False)
        st.dataframe(df_overdue, use_container_width=True)
    else:
        st.success("🎉 No overdue tasks!")

def show_data_management():
    """Display data management page"""
    if not can_access_data_management():
        st.error("🚫 Access Denied: Only administrators can access data management.")
        return
    
    st.title("💾 Data Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Export Data")
        
        if st.button("📥 Download All Data (JSON)"):
            data_json = json.dumps(st.session_state.data, indent=2, default=str)
            st.download_button(
                label="Download JSON",
                data=data_json,
                file_name=f"problem_tracker_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        if st.button("📊 Export Summary to CSV"):
            if st.session_state.data['problem_files']:
                summary_data = []
                for file_id, file_data in st.session_state.data['problem_files'].items():
                    progress = calculate_project_progress(file_data['tasks'])
                    summary_data.append({
                        'Problem File': file_data['problem_name'],
                        'Owner': file_data['owner'],
                        'Progress': progress,
                        'Start Date': file_data['project_start_date'].strftime('%Y-%m-%d'),
                        'Last Modified': file_data['last_modified'].strftime('%Y-%m-%d %H:%M')
                    })
                
                df = pd.DataFrame(summary_data)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"problem_tracker_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    with col2:
        st.subheader("Database Status")
        
        try:
            supabase = init_supabase()
            # Test connection
            test_response = supabase.table('problem_files').select('*').limit(1).execute()
            st.success("✅ Connected to Supabase database")
            
            # Show database stats
            files_count = supabase.table('problem_files').select('*', count='exact').execute()
            tasks_count = supabase.table('tasks').select('*', count='exact').execute()
            subtasks_count = supabase.table('subtasks').select('*', count='exact').execute()
            
            st.info(f"📊 Database Stats:\n- Problem Files: {files_count.count}\n- Tasks: {tasks_count.count}\n- Subtasks: {subtasks_count.count}")
            
        except Exception as e:
            st.error(f"❌ Database connection error: {e}")
    
    st.subheader("User Management")
    
    # Current users
    st.write("**Current Users:**")
    for user in st.session_state.data['users']:
        col1, col2 = st.columns([3, 1])
        with col1:
            role = "Admin" if user == "Admin" else "User"
            st.write(f"• {user} (Role: {role})")
        with col2:
            if user != 'Admin':
                st.write("👤 User")
    
    st.info("💡 **Note**: User management is now handled through Streamlit secrets. Update the credentials section in your app settings to add/remove users.")
    
    # Refresh data button
    st.subheader("🔄 Data Refresh")
    if st.button("🔄 Refresh Data from Database"):
        load_data()
        st.success("✅ Data refreshed from Supabase!")
        st.rerun()

# Main application logic
def main():
    # Load data after authentication
    if st.session_state.authenticated:
        load_data()

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