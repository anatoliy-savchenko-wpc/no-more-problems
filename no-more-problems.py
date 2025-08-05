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
if 'data' not in st.session_state:
    st.session_state.data = {
        'problem_files': {},
        'users': list(USER_CREDENTIALS.keys())  # Use keys from credentials file
    }

if 'current_file_id' not in st.session_state:
    st.session_state.current_file_id = None

# Authentication state - default to False to force login
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if 'current_user' not in st.session_state:
    st.session_state.current_user = None

if 'user_role' not in st.session_state:
    st.session_state.user_role = None

# Page state for navigation
if 'page' not in st.session_state:
    st.session_state.page = "Dashboard"

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

# Legacy function - now replaced by Supabase functions
def save_data():
    """Legacy function - individual saves now handle persistence"""
    pass

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

# Load data after authentication
if st.session_state.authenticated:
    load_data()

# Main application logic
if not st.session_state.authenticated:
    # Clear any existing session data when not authenticated
    if st.session_state.current_user is not None:
        st.session_state.current_user = None
        st.session_state.user_role = None
        st.session_state.current_file_id = None
    
    show_login_form()
else:
    # Sidebar with user info and navigation
    st.sidebar.title("🔧 Problem File Tracker")
    
    # User info and logout
    st.sidebar.markdown(f"👤 **Logged in as:** {st.session_state.current_user}")
    st.sidebar.markdown(f"🔑 **Role:** {st.session_state.user_role}")
    
    if st.sidebar.button("🚪 Logout"):
        logout()
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Navigation menu (filtered by permissions)
    nav_options = ["Dashboard", "Manage Problem Files", "Executive Summary"]
    if can_access_data_management():
        nav_options.append("Data Management")
    
    # Use session state for page selection
    page = st.sidebar.selectbox("Navigate to:", nav_options, index=nav_options.index(st.session_state.page) if st.session_state.page in nav_options else 0)
    
    # Update session state when page changes
    if page != st.session_state.page:
        st.session_state.page = page

    # Main content based on page selection
    if page == "Dashboard":
        st.title("📊 Problem File Tracker Dashboard")
        
        accessible_files = get_accessible_files()
        
        if not accessible_files:
            st.info("No problem files available. Create a new one or ask an admin for access!")
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
                        st.session_state.current_file_id = file_id
                        # Switch to Manage Problem Files page
                        st.session_state.page = "Manage Problem Files"
                        st.rerun()
            
            # Recent Notes and Comments Section (filtered by accessible files)
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
                    
                    # Show detailed notes in expandable sections
                    st.subheader("📋 Detailed Notes")
                    for idx, row in filtered_notes.iterrows():
                        with st.expander(f"{row['Project']} - {row['Task']} ({row['Assigned To']})"):
                            col1, col2 = st.columns([2, 1])
                            with col1:
                                st.write(f"**Notes:** {row['Notes']}")
                            with col2:
                                st.write(f"**Progress:** {row['Progress']}")
                                st.write(f"**Due Date:** {row['Due Date']}")
                                st.write(f"**Status:** {row['Status']}")
                else:
                    st.info("No notes match the selected filters.")
            else:
                st.info("No notes or comments found. Add some notes to your tasks to see them here!")

    elif page == "Manage Problem Files":
        st.title("🛠️ Manage Problem Files")
        
        # Create new problem file section
        with st.expander("➕ Create New Problem File", expanded=False):
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
                
                if st.form_submit_button("Create Problem File"):
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
                            st.rerun()
                        else:
                            st.error("Failed to create problem file.")
                    else:
                        st.error("Please fill in all required fields.")
        
        # Select and edit existing problem file
        accessible_files = get_accessible_files()
        
        if accessible_files:
            st.subheader("Edit Existing Problem File")
            
            # File selection (only accessible files)
            file_options = {file_id: f"{data['problem_name']} ({data['owner']})" 
                           for file_id, data in accessible_files.items()}
            
            selected_file_id = st.selectbox(
                "Select Problem File to Edit:",
                options=list(file_options.keys()),
                format_func=lambda x: file_options[x],
                index=0 if not st.session_state.current_file_id else list(file_options.keys()).index(st.session_state.current_file_id) if st.session_state.current_file_id in file_options else 0
            )
            
            if selected_file_id:
                st.session_state.current_file_id = selected_file_id
                problem_file = st.session_state.data['problem_files'][selected_file_id]
                
                # Check if user can edit this file
                can_edit = can_edit_file(problem_file['owner'])
                
                if not can_edit:
                    st.warning("You can only view this file. Contact the owner or admin to make changes.")
                
                # Check for overdue tasks and update (only if can edit)
                if can_edit and check_overdue_and_update(problem_file):
                    st.warning("Some overdue tasks have been automatically updated with new deadlines.")
                
                # File metadata editing (only if can edit)
                if can_edit:
                    with st.expander("📝 Edit File Metadata"):
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
                            
                            if st.form_submit_button("Update Metadata"):
                                problem_file['problem_name'] = new_name
                                problem_file['owner'] = new_owner
                                problem_file['project_start_date'] = datetime.combine(new_start_date, datetime.min.time())
                                problem_file['display_week'] = new_display_week
                                problem_file['last_modified'] = datetime.now()
                                
                                if save_problem_file(selected_file_id, problem_file):
                                    st.success("Metadata updated successfully!")
                                    st.rerun()
                                else:
                                    st.error("Failed to update metadata.")
                
                # Task management
                st.subheader("📋 Task Management")
                
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
                                    
                                    if save_task(selected_file_id, task_id, task_data):
                                        problem_file['tasks'][task_id] = task_data
                                        st.success(f"Main task '{task_name}' added!")
                                        st.rerun()
                                    else:
                                        st.error("Failed to add task.")
                
                # Display and manage existing tasks
                for task_id, task in problem_file['tasks'].items():
                    with st.expander(f"📂 {task['name']}", expanded=True):
                        
                        # Task header with delete option (only if can edit and delete)
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
                        
                        # Add subtask (only if can edit)
                        if can_edit:
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
                                
                                    submitted = st.form_submit_button("Add Subtask")
                                if submitted:
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
                                            problem_file['last_modified'] = datetime.now()
                                            st.success(f"Subtask '{subtask_name}' added!")
                                            st.rerun()
                                        else:
                                            st.error("Failed to add subtask.")
                                    else:
                                        st.error("Please fill in required fields.")
                        
                        # Display and edit existing subtasks
                        if task['subtasks']:
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
                            st.dataframe(df_subtasks, use_container_width=True)
                            
                            # Edit subtask (only if can edit)
                            if can_edit:
                                subtask_to_edit = st.selectbox(
                                    f"Select subtask to edit:",
                                    options=[None] + list(task['subtasks'].keys()),
                                    format_func=lambda x: "Select..." if x is None else task['subtasks'][x]['name'],
                                    key=f"edit_select_{task_id}"
                                )
                                
                                if subtask_to_edit:
                                    subtask = task['subtasks'][subtask_to_edit]
                                    # Check if user can edit this specific subtask
                                    can_edit_subtask = (st.session_state.user_role == 'Admin' or 
                                                       problem_file['owner'] == st.session_state.current_user or
                                                       subtask['assigned_to'] == st.session_state.current_user)
                                    
                                    if can_edit_subtask:
                                        with st.form(f"edit_subtask_{task_id}_{subtask_to_edit}"):
                                            st.write(f"**Editing: {subtask['name']}**")
                                            ecol1, ecol2, ecol3 = st.columns(3)
                                            with ecol1:
                                                new_subtask_name = st.text_input("Subtask Name", value=subtask['name'], key=f"edit_name_{task_id}_{subtask_to_edit}")
                                                # Only admin and owner can reassign tasks
                                                if st.session_state.user_role == 'Admin' or problem_file['owner'] == st.session_state.current_user:
                                                    new_assigned_to = st.selectbox("Assigned To", st.session_state.data['users'],
                                                                                 index=st.session_state.data['users'].index(subtask['assigned_to']),
                                                                                 key=f"edit_assigned_{task_id}_{subtask_to_edit}")
                                                else:
                                                    new_assigned_to = subtask['assigned_to']
                                                    st.write(f"**Assigned To:** {new_assigned_to}")
                                            with ecol2:
                                                new_start_date = st.date_input("Start Date", value=subtask['start_date'].date(), key=f"edit_start_{task_id}_{subtask_to_edit}")
                                                new_progress = st.slider("Progress %", 0, 100, subtask['progress'], key=f"edit_progress_{task_id}_{subtask_to_edit}")
                                            with ecol3:
                                                new_end_date = st.date_input("Projected End Date", 
                                                                           value=subtask['projected_end_date'].date(),
                                                                           key=f"edit_end_{task_id}_{subtask_to_edit}")
                                                new_notes = st.text_area("Notes", value=subtask['notes'], key=f"edit_notes_{task_id}_{subtask_to_edit}")
                                            
                                            col_update, col_delete = st.columns(2)
                                            with col_update:
                                                submitted_update = st.form_submit_button("Update Subtask")
                                                if submitted_update:
                                                    subtask['name'] = new_subtask_name
                                                    subtask['assigned_to'] = new_assigned_to
                                                    subtask['start_date'] = datetime.combine(new_start_date, datetime.min.time())
                                                    subtask['projected_end_date'] = datetime.combine(new_end_date, datetime.min.time())
                                                    subtask['progress'] = new_progress
                                                    subtask['notes'] = new_notes
                                                    
                                                    if save_subtask(task_id, subtask_to_edit, subtask):
                                                        problem_file['last_modified'] = datetime.now()
                                                        st.success("Subtask updated!")
                                                        st.rerun()
                                                    else:
                                                        st.error("Failed to update subtask.")
                                            
                                            with col_delete:
                                                if can_delete_items():
                                                    submitted_delete = st.form_submit_button("Delete Subtask", type="secondary")
                                                    if submitted_delete:
                                                        if delete_subtask(subtask_to_edit):
                                                            del task['subtasks'][subtask_to_edit]
                                                            problem_file['last_modified'] = datetime.now()
                                                            st.success("Subtask deleted!")
                                                            st.rerun()
                                                        else:
                                                            st.error("Failed to delete subtask.")
                                    else:
                                        st.info("You can only edit subtasks assigned to you.")
                
                # Gantt Chart
                st.subheader("📈 Gantt Chart")
                gantt_fig = create_gantt_chart(problem_file)
                if gantt_fig:
                    st.plotly_chart(gantt_fig, use_container_width=True)
                else:
                    st.info("No tasks to display in Gantt chart. Add some subtasks first!")

    elif page == "Executive Summary":
        st.title("📊 Executive Summary")
        
        accessible_files = get_accessible_files()
        
        if not accessible_files:
            st.info("No problem files to summarize.")
        else:
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
            
            # Detailed overdue tasks (filtered by accessible files)
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

    elif page == "Data Management":
        if not can_access_data_management():
            st.error("🚫 Access Denied: Only administrators can access data management.")
        else:
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
            for i, user in enumerate(st.session_state.data['users']):
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

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("🔧 **Problem File Tracker v3.0 (Supabase)**")
    st.sidebar.markdown(f"Last loaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.sidebar.markdown("🗄️ **Database**: Supabase (Persistent)")