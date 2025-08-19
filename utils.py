"""
Utility functions for permissions and calculations with universal view access
"""
import streamlit as st
from datetime import datetime, timedelta

# ====== PERMISSION CHECKING FUNCTIONS ======

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
    """Check if user can edit a specific file (legacy function)"""
    return st.session_state.user_role in ['Admin', 'Partner'] or st.session_state.current_user == file_owner

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

def can_manage_contacts(file_owner):
    """Check if user can manage contacts for a file (legacy function)"""
    return st.session_state.user_role in ['Admin', 'Partner'] or st.session_state.current_user == file_owner

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

def can_edit_contact(contact_id):
    """Check if user can edit a specific contact"""
    if contact_id not in st.session_state.data.get('contacts', {}):
        return False
    
    contact = st.session_state.data['contacts'][contact_id]
    file_id = contact.get('problem_file_id')
    
    # Can edit if user can edit the file
    if can_edit_specific_file(file_id):
        return True
    
    # Contact creator can edit their own contacts
    if contact.get('added_by') == st.session_state.current_user:
        return True
    
    return False

def can_delete_contact(contact_id):
    """Check if user can delete a specific contact"""
    if contact_id not in st.session_state.data.get('contacts', {}):
        return False
    
    contact = st.session_state.data['contacts'][contact_id]
    
    # Admin and Partners can delete any contact
    if st.session_state.user_role in ['Admin', 'Partner']:
        return True
    
    # Contact creator can delete their own contacts
    if contact.get('added_by') == st.session_state.current_user:
        return True
    
    return False

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

def can_assign_files():
    """Check if user can assign files to others"""
    return st.session_state.user_role in ['Admin', 'Partner']

def can_view_all_analytics():
    """Check if user can view analytics for all files"""
    return st.session_state.user_role in ['Admin', 'Partner']

def get_user_role_display():
    """Get display-friendly user role"""
    role = st.session_state.user_role
    if role == 'Admin':
        return "👑 Administrator"
    elif role == 'Partner':
        return "🤝 Partner"
    else:
        return "👤 User"

# ====== CALCULATION FUNCTIONS ======

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

# ====== DATA ACCESS FUNCTIONS - UNIVERSAL VIEW ======

def get_accessible_files():
    """Get all problem files - everyone can see everything now"""
    return st.session_state.data.get('problem_files', {})

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

def get_user_owned_files():
    """Get files owned by the current user"""
    owned_files = {}
    current_user = st.session_state.current_user
    
    for file_id, file_data in st.session_state.data.get('problem_files', {}).items():
        if file_data.get('owner') == current_user:
            owned_files[file_id] = file_data
    
    return owned_files

def get_user_accessible_files():
    """Get files where user has some level of access (for dashboard metrics)"""
    accessible_files = {}
    current_user = st.session_state.current_user
    
    for file_id, file_data in st.session_state.data.get('problem_files', {}).items():
        # Everyone can see all files, but track which ones they have edit access to
        user_can_edit = can_edit_specific_file(file_id)
        
        accessible_files[file_id] = {
            **file_data,
            'user_can_edit': user_can_edit,
            'user_is_owner': file_data.get('owner') == current_user,
            'user_is_assigned': any(
                subtask.get('assigned_to') == current_user
                for task in file_data.get('tasks', {}).values()
                for subtask in task.get('subtasks', {}).values()
            )
        }
    
    return accessible_files

# ====== ANALYTICS AND STATISTICS ======

def get_user_statistics(user_name=None):
    """Get comprehensive statistics for a user"""
    if user_name is None:
        user_name = st.session_state.current_user
    
    try:
        # Count owned files
        owned_files = len([f for f in st.session_state.data.get('problem_files', {}).values() 
                          if f['owner'] == user_name])
        
        # Count assigned subtasks
        assigned_subtasks = 0
        completed_subtasks = 0
        for file_data in st.session_state.data.get('problem_files', {}).values():
            for task in file_data.get('tasks', {}).values():
                for subtask in task.get('subtasks', {}).values():
                    if subtask['assigned_to'] == user_name:
                        assigned_subtasks += 1
                        if subtask['progress'] == 100:
                            completed_subtasks += 1
        
        # Count comments
        user_comments = len([c for c in st.session_state.data.get('comments', {}).values() 
                           if c['user_name'] == user_name])
        
        # Count resolved comments
        resolved_comments = len([c for c in st.session_state.data.get('comments', {}).values() 
                               if c['resolved_by'] == user_name])
        
        # Count events created
        user_events = len([e for e in st.session_state.data.get('event_logs', {}).values() 
                          if e['created_by'] == user_name])
        
        # Count contacts added
        user_contacts = len([c for c in st.session_state.data.get('contacts', {}).values() 
                           if c['added_by'] == user_name])
        
        return {
            'owned_files': owned_files,
            'assigned_subtasks': assigned_subtasks,
            'completed_subtasks': completed_subtasks,
            'completion_rate': (completed_subtasks / assigned_subtasks * 100) if assigned_subtasks > 0 else 0,
            'user_comments': user_comments,
            'resolved_comments': resolved_comments,
            'user_events': user_events,
            'user_contacts': user_contacts
        }
        
    except Exception as e:
        st.error(f"Error getting user statistics: {e}")
        return {
            'owned_files': 0,
            'assigned_subtasks': 0,
            'completed_subtasks': 0,
            'completion_rate': 0,
            'user_comments': 0,
            'resolved_comments': 0,
            'user_events': 0,
            'user_contacts': 0
        }

def get_overdue_tasks_count():
    """Get count of overdue tasks across all accessible files"""
    today = datetime.now().date()
    overdue_count = 0
    
    for file_data in get_accessible_files().values():
        for task in file_data.get('tasks', {}).values():
            for subtask in task.get('subtasks', {}).values():
                if (subtask['projected_end_date'].date() < today and 
                    subtask['progress'] < 100):
                    overdue_count += 1
    
    return overdue_count

def get_completion_rate_by_user():
    """Get completion rates for all users"""
    user_stats = {}
    
    for file_data in st.session_state.data.get('problem_files', {}).values():
        for task in file_data.get('tasks', {}).values():
            for subtask in task.get('subtasks', {}).values():
                user = subtask['assigned_to']
                if user not in user_stats:
                    user_stats[user] = {'total': 0, 'completed': 0}
                
                user_stats[user]['total'] += 1
                if subtask['progress'] == 100:
                    user_stats[user]['completed'] += 1
    
    # Calculate completion rates
    completion_rates = {}
    for user, stats in user_stats.items():
        completion_rates[user] = (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
    
    return completion_rates

# ====== FILE FILTERING AND SORTING ======

def filter_files_by_status(files, status_filter):
    """Filter files by completion status"""
    if status_filter == "All":
        return files
    elif status_filter == "Completed":
        return {fid: f for fid, f in files.items() if calculate_project_progress(f['tasks']) >= 100}
    elif status_filter == "In Progress":
        return {fid: f for fid, f in files.items() if 0 < calculate_project_progress(f['tasks']) < 100}
    elif status_filter == "Not Started":
        return {fid: f for fid, f in files.items() if calculate_project_progress(f['tasks']) == 0}
    else:
        return files

def sort_files_by_criteria(files, sort_criteria):
    """Sort files by various criteria"""
    if sort_criteria == "Name":
        return dict(sorted(files.items(), key=lambda x: x[1]['problem_name']))
    elif sort_criteria == "Owner":
        return dict(sorted(files.items(), key=lambda x: x[1]['owner']))
    elif sort_criteria == "Progress":
        return dict(sorted(files.items(), key=lambda x: calculate_project_progress(x[1]['tasks']), reverse=True))
    elif sort_criteria == "Last Modified":
        return dict(sorted(files.items(), key=lambda x: x[1].get('last_modified', datetime.min), reverse=True))
    elif sort_criteria == "Created Date":
        return dict(sorted(files.items(), key=lambda x: x[1].get('created_date', datetime.min), reverse=True))
    else:
        return files