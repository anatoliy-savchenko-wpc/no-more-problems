"""
Database operations module for Supabase integration
"""
import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client, Client

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    """Initialize Supabase client"""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

# Helper function to parse dates safely
def safe_parse_date(date_str):
    """Parse dates safely from database"""
    if isinstance(date_str, str):
        date_str = date_str.replace('Z', '+00:00')
        if '+00:00' not in date_str and 'T' in date_str:
            date_str += '+00:00'
        return datetime.fromisoformat(date_str)
    return date_str if isinstance(date_str, datetime) else datetime.now()

# Load data functions
def load_data():
    """Load all data from Supabase into session state"""
    if not st.session_state.authenticated:
        return
        
    try:
        supabase = init_supabase()
        
        # Load problem files with user filtering
        if st.session_state.user_role in ['Admin', 'Partner']:
            # Admin and Partners see all files
            problem_files_response = supabase.table('problem_files').select('*').execute()
        else:
            # Regular users see files they own or are assigned to
            owned_files = supabase.table('problem_files').select('*').eq('owner', st.session_state.current_user).execute()
            
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
            
            problem_files[file_id] = {
                'problem_name': pf['problem_name'],
                'owner': pf['owner'],
                'project_start_date': safe_parse_date(pf['project_start_date']),
                'project_end_date': safe_parse_date(pf.get('project_end_date', pf['project_start_date'])),
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
        
        # Load comments and contacts
        load_comments()
        load_contacts()
        
    except Exception as e:
        st.error(f"Error loading data from Supabase: {e}")
        st.session_state.data['problem_files'] = {}

def load_comments():
    """Load comments from Supabase"""
    try:
        supabase = init_supabase()
        comments_response = supabase.table('comments').select('*').execute()
        
        comments = {}
        for comment in comments_response.data:
            comment_id = comment['id']
            
            # Parse created_at date safely
            created_at = comment.get('created_at')
            if created_at:
                created_at = safe_parse_date(created_at)
            else:
                created_at = datetime.now()
            
            comments[comment_id] = {
                'entity_type': comment.get('entity_type', ''),
                'entity_id': comment.get('entity_id', ''),
                'user_name': comment.get('user_name', ''),
                'text': comment.get('text', ''),
                'created_at': created_at,
                'parent_id': comment.get('parent_id'),
                'user_role': comment.get('user_role', 'User')
            }
        
        st.session_state.data['comments'] = comments
        
    except Exception as e:
        st.error(f"Error loading comments: {e}")
        st.session_state.data['comments'] = {}

def load_contacts():
    """Load contacts from Supabase"""
    try:
        supabase = init_supabase()
        contacts_response = supabase.table('contacts').select('*').execute()
        
        contacts = {}
        for contact in contacts_response.data:
            contact_id = contact['id']
            contacts[contact_id] = {
                'problem_file_id': contact['problem_file_id'],
                'name': contact['name'],
                'organization': contact.get('organization', ''),
                'title': contact.get('title', ''),
                'email': contact.get('email', ''),
                'telephone': contact.get('telephone', ''),
                'comments': contact.get('comments', ''),
                'added_by': contact.get('added_by', ''),
                'created_at': safe_parse_date(contact['created_at'])
            }
        
        st.session_state.data['contacts'] = contacts
        
    except Exception as e:
        st.error(f"Error loading contacts: {e}")
        st.session_state.data['contacts'] = {}

# Save functions
def save_problem_file(file_id: str, file_data: dict):
    """Save or update a problem file"""
    try:
        supabase = init_supabase()
        
        db_data = {
            'id': file_id,
            'problem_name': file_data['problem_name'],
            'owner': file_data['owner'],
            'project_start_date': file_data['project_start_date'].isoformat(),
            'project_end_date': file_data.get('project_end_date', file_data['project_start_date'] + timedelta(days=30)).isoformat(),
            'display_week': file_data['display_week'],
            'created_date': file_data.get('created_date', datetime.now()).isoformat(),
            'last_modified': datetime.now().isoformat()
        }
        
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

def save_comment(comment_id: str, comment_data: dict):
    """Save a comment to Supabase"""
    try:
        supabase = init_supabase()
        
        # Prepare the data matching your schema
        db_data = {
            'id': comment_id,
            'entity_type': comment_data.get('entity_type', ''),
            'entity_id': comment_data.get('entity_id', ''),
            'user_name': comment_data.get('user_name', ''),
            'text': comment_data.get('text', ''),
            'parent_id': comment_data.get('parent_id'),
            'user_role': comment_data.get('user_role', 'User')
        }
        
        supabase.table('comments').upsert(db_data).execute()
        return True
        
    except Exception as e:
        st.error(f"Error saving comment: {e}")
        st.error(f"Debug - Comment data: {db_data}")
        return False

def save_contact(contact_id: str, contact_data: dict):
    """Save a contact to Supabase"""
    try:
        supabase = init_supabase()
        
        db_data = {
            'id': contact_id,
            'problem_file_id': contact_data['problem_file_id'],
            'name': contact_data['name'],
            'organization': contact_data.get('organization', ''),
            'title': contact_data.get('title', ''),
            'email': contact_data.get('email', ''),
            'telephone': contact_data.get('telephone', ''),
            'comments': contact_data.get('comments', ''),
            'added_by': contact_data.get('added_by', ''),
            'created_at': contact_data['created_at'].isoformat()
        }
        
        supabase.table('contacts').upsert(db_data).execute()
        return True
        
    except Exception as e:
        st.error(f"Error saving contact: {e}")
        return False

# Delete functions
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

def delete_comment(comment_id: str):
    """Delete a comment from Supabase"""
    try:
        supabase = init_supabase()
        supabase.table('comments').delete().eq('id', comment_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting comment: {e}")
        return False

def delete_contact(contact_id: str):
    """Delete a contact from Supabase"""
    try:
        supabase = init_supabase()
        supabase.table('contacts').delete().eq('id', contact_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting contact: {e}")
        return False