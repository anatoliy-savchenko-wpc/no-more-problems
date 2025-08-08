"""
Utility functions for permissions and calculations
"""
import streamlit as st
from datetime import datetime, timedelta

# Permission checking functions
def can_access_data_management():
    """Check if user can access data management"""
    return st.session_state.user_role == 'Admin'

def can_delete_items():
    """Check if user can delete items"""
    return st.session_state.user_role in ['Admin', 'Partner']

def can_edit_all_files():
    """Check if user can edit all problem files"""
    return st.session_state.user_role in ['Admin', 'Partner']

def can_create_files():
    """Check if user can create problem files"""
    return st.session_state.user_role in ['Admin', 'Partner', 'User']

def can_edit_file(file_owner):
    """Check if user can edit a specific file"""
    return st.session_state.user_role in ['Admin', 'Partner'] or st.session_state.current_user == file_owner

def can_manage_contacts(file_owner):
    """Check if user can manage contacts for a file"""
    return st.session_state.user_role in ['Admin', 'Partner'] or st.session_state.current_user == file_owner

# Calculation functions
def calculate_task_progress(subtasks):
    """Calculate task progress based on subtasks"""
    if not subtasks:
        return 0
    total_progress = sum(subtask['progress'] for subtask in subtasks.values())
    return total_progress / len(subtasks)

def calculate_project_progress(tasks):
    """Calculate overall project progress"""
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

def check_overdue_and_update(problem_file):
    """Check for overdue tasks and update them"""
    from database import save_subtask
    
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

def get_accessible_files():
    """Get files accessible to current user"""
    if not st.session_state.authenticated:
        return {}
    
    if st.session_state.user_role in ['Admin', 'Partner']:
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