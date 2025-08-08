"""
Problem files management pages
"""
import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, timedelta
from database import (save_problem_file, save_task, save_subtask, delete_problem_file, 
                     delete_task, delete_subtask)
from utils import (get_accessible_files, calculate_project_progress, can_edit_file, 
                  can_delete_items, check_overdue_and_update)
from components.tasks import show_task_management
from components.visualization import show_gantt_chart_tab, show_file_analytics
from components.contacts import show_contacts_section
from components.settings import show_file_settings

def show_create_problem_file():
    """Display create problem file page"""
    st.title("➕ Create New Problem File")
    
    with st.form("new_problem_file"):
        col1, col2 = st.columns(2)
        with col1:
            problem_name = st.text_input("Problem Name*")
            # Admin and Partners can assign to any user, others default to themselves
            if st.session_state.user_role in ['Admin', 'Partner']:
                owner = st.selectbox("Owner*", st.session_state.data['users'])
            else:
                owner = st.session_state.current_user
                st.write(f"**Owner:** {owner}")
        with col2:
            project_start_date = st.date_input("Project Start Date*", datetime.now())
            project_end_date = st.date_input("Project End Date*", 
                                            datetime.now() + timedelta(days=30),
                                            min_value=project_start_date)
            display_week = st.number_input("Display Week", min_value=1, value=1)
        
        # Show project duration
        if project_end_date >= project_start_date:
            duration = (project_end_date - project_start_date).days
            st.info(f"📅 Project Duration: {duration} days")
        
        description = st.text_area("Problem Description (Optional)")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Create Problem File", use_container_width=True):
                if problem_name and project_end_date >= project_start_date:
                    file_id = str(uuid.uuid4())
                    file_data = {
                        'problem_name': problem_name,
                        'owner': owner,
                        'project_start_date': datetime.combine(project_start_date, datetime.min.time()),
                        'project_end_date': datetime.combine(project_end_date, datetime.min.time()),
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
                elif project_end_date < project_start_date:
                    st.error("End date must be after start date!")
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
        
        # Count comments and contacts
        comments_count = 0
        for task in file_data['tasks'].values():
            comments_count += len([c for c in st.session_state.data.get('comments', {}).values() 
                                 if c['entity_type'] == 'task' and c['entity_id'] in file_data['tasks']])
            for subtask_id in task['subtasks']:
                comments_count += len([c for c in st.session_state.data.get('comments', {}).values() 
                                     if c['entity_type'] == 'subtask' and c['entity_id'] == subtask_id])
        
        contacts_count = len([c for c in st.session_state.data.get('contacts', {}).values() 
                            if c['problem_file_id'] == file_id])
        
        files_data.append({
            'ID': file_id,
            'Name': file_data['problem_name'],
            'Owner': file_data['owner'],
            'Progress': f"{progress:.1f}%",
            'Comments': comments_count,
            'Contacts': contacts_count,
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
            if can_delete_items() and selected_file_data['owner'] == st.session_state.current_user:
                if st.button("🗑️ Delete File", use_container_width=True, type="secondary"):
                    st.session_state.file_to_delete = selected_file_id
                    st.rerun()

        
        # Handle file deletion confirmation
        if hasattr(st.session_state, 'file_to_delete') and st.session_state.file_to_delete:
            file_to_delete = st.session_state.file_to_delete
            file_name = accessible_files[file_to_delete]['problem_name']
            
            st.error(f"⚠️ **Confirm Deletion of '{file_name}'**")
            st.warning("This action cannot be undone. All tasks, subtasks, comments, and contacts will be permanently deleted.")
            
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
    col1, col2, col3, col4, col5 = st.columns(5)
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
    with col5:
        contacts_count = len([c for c in st.session_state.data.get('contacts', {}).values() 
                            if c['problem_file_id'] == file_id])
        st.metric("Contacts", contacts_count)
    
    # Check permissions
    can_edit = can_edit_file(problem_file['owner'])
    
    if not can_edit and st.session_state.user_role != 'Partner':
        st.info("👁️ **View Only Mode** - You can view this file but cannot make changes. Contact the owner or a partner for edit access.")
    
    # Check for overdue tasks and update (only if can edit)
    if can_edit and check_overdue_and_update(problem_file):
        st.warning("Some overdue tasks have been automatically updated with new deadlines.")
    
    # Navigation tabs
    tabs = st.tabs(["📋 Tasks & Subtasks", "📊 Gantt Chart", "📇 Contacts", "📝 File Settings", "📈 Analytics"])
    
    with tabs[0]:
        show_task_management(file_id, problem_file, can_edit)
    
    with tabs[1]:
        show_gantt_chart_tab(problem_file)
    
    with tabs[2]:
        show_contacts_section(file_id, problem_file)
    
    with tabs[3]:
        show_file_settings(file_id, problem_file, can_edit)
    
    with tabs[4]:
        show_file_analytics(problem_file)