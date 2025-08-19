"""
SharePoint Links Component for Tasks and Subtasks
"""
import streamlit as st
import pandas as pd
import uuid
import re
from datetime import datetime
from database import save_sharepoint_link, delete_sharepoint_link

def show_sharepoint_links_section(file_id, problem_file, can_edit):
    """Display SharePoint links management for tasks and subtasks"""
    
    st.subheader("🔗 SharePoint Document Links")
    st.write("Manage SharePoint folder links for your tasks and subtasks.")
    
    # Add new SharePoint link (only if can edit)
    if can_edit:
        with st.expander("➕ Add New SharePoint Link"):
            with st.form("new_sharepoint_link"):
                # Get available tasks and subtasks
                task_options = {}
                for task_id, task in problem_file.get('tasks', {}).items():
                    task_options[f"Task: {task['name']}"] = {'type': 'task', 'id': task_id}
                    for subtask_id, subtask in task.get('subtasks', {}).items():
                        task_options[f"  └─ Subtask: {subtask['name']}"] = {'type': 'subtask', 'id': subtask_id}
                
                if not task_options:
                    st.info("No tasks available. Create tasks first before adding SharePoint links.")
                    st.stop()
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    selected_item = st.selectbox("Link to Task/Subtask*", list(task_options.keys()))
                    sharepoint_url = st.text_input("SharePoint URL*", 
                                                  placeholder="https://yourcompany.sharepoint.com/sites/...")
                    link_description = st.text_area("Description (Optional)", 
                                                   placeholder="Describe what documents are in this folder...")
                
                with col2:
                    link_type = st.selectbox("Link Type", [
                        "Document Library", "Folder", "Specific Document", 
                        "Site", "List", "Other"
                    ])
                    access_level = st.selectbox("Access Level", [
                        "Team Access", "Public", "Restricted", "Owner Only"
                    ])
                
                if st.form_submit_button("Add SharePoint Link", use_container_width=True):
                    if selected_item and sharepoint_url:
                        if validate_sharepoint_url(sharepoint_url):
                            link_id = str(uuid.uuid4())
                            selected_data = task_options[selected_item]
                            
                            link_data = {
                                'problem_file_id': file_id,
                                'entity_type': selected_data['type'],
                                'entity_id': selected_data['id'],
                                'url': sharepoint_url,
                                'description': link_description,
                                'link_type': link_type,
                                'access_level': access_level,
                                'created_by': st.session_state.current_user,
                                'created_at': datetime.now()
                            }
                            
                            if save_sharepoint_link(link_id, link_data):
                                # Add to session state for immediate display
                                if 'sharepoint_links' not in st.session_state.data:
                                    st.session_state.data['sharepoint_links'] = {}
                                st.session_state.data['sharepoint_links'][link_id] = link_data
                                st.success("SharePoint link added successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to add SharePoint link.")
                        else:
                            st.error("Please enter a valid SharePoint URL.")
                    else:
                        st.error("Please fill in all required fields.")
    
    # Display existing SharePoint links
    sharepoint_links = get_file_sharepoint_links(file_id)
    
    if not sharepoint_links:
        st.info("No SharePoint links added yet. Add links above to connect your tasks with document folders!")
        return
    
    # Group links by task/subtask
    grouped_links = group_links_by_entity(sharepoint_links, problem_file)
    
    # Display links grouped by task
    for task_id, task_data in grouped_links.items():
        if task_id in problem_file.get('tasks', {}):
            task_name = problem_file['tasks'][task_id]['name']
            
            with st.expander(f"📂 {task_name}", expanded=True):
                # Task-level links
                if 'task_links' in task_data:
                    st.write("**Task-level SharePoint Links:**")
                    for link_id, link in task_data['task_links'].items():
                        display_sharepoint_link(link_id, link, can_edit)
                
                # Subtask-level links
                if 'subtask_links' in task_data:
                    for subtask_id, subtask_links in task_data['subtask_links'].items():
                        if subtask_id in problem_file['tasks'][task_id]['subtasks']:
                            subtask_name = problem_file['tasks'][task_id]['subtasks'][subtask_id]['name']
                            st.write(f"**└─ {subtask_name} - SharePoint Links:**")
                            for link_id, link in subtask_links.items():
                                display_sharepoint_link(link_id, link, can_edit, is_subtask=True)

def get_file_sharepoint_links(file_id):
    """Get all SharePoint links for a specific problem file"""
    all_links = st.session_state.data.get('sharepoint_links', {})
    return {lid: link for lid, link in all_links.items() 
            if link.get('problem_file_id') == file_id}

def group_links_by_entity(links, problem_file):
    """Group SharePoint links by their parent task"""
    grouped = {}
    
    for link_id, link in links.items():
        entity_type = link.get('entity_type')
        entity_id = link.get('entity_id')
        
        if entity_type == 'task':
            if entity_id not in grouped:
                grouped[entity_id] = {}
            if 'task_links' not in grouped[entity_id]:
                grouped[entity_id]['task_links'] = {}
            grouped[entity_id]['task_links'][link_id] = link
            
        elif entity_type == 'subtask':
            # Find parent task
            parent_task_id = None
            for task_id, task in problem_file.get('tasks', {}).items():
                if entity_id in task.get('subtasks', {}):
                    parent_task_id = task_id
                    break
            
            if parent_task_id:
                if parent_task_id not in grouped:
                    grouped[parent_task_id] = {}
                if 'subtask_links' not in grouped[parent_task_id]:
                    grouped[parent_task_id]['subtask_links'] = {}
                if entity_id not in grouped[parent_task_id]['subtask_links']:
                    grouped[parent_task_id]['subtask_links'][entity_id] = {}
                grouped[parent_task_id]['subtask_links'][entity_id][link_id] = link
    
    return grouped

def display_sharepoint_link(link_id, link, can_edit, is_subtask=False):
    """Display an individual SharePoint link"""
    # Link type icons
    type_icons = {
        "Document Library": "📚",
        "Folder": "📁",
        "Specific Document": "📄",
        "Site": "🌐",
        "List": "📋",
        "Other": "🔗"
    }
    
    # Access level colors
    access_colors = {
        "Team Access": "🟢",
        "Public": "🔵",
        "Restricted": "🟡",
        "Owner Only": "🔴"
    }
    
    icon = type_icons.get(link.get('link_type', 'Other'), "🔗")
    access_icon = access_colors.get(link.get('access_level', 'Team Access'), "🟢")
    
    indent = "    " if is_subtask else ""
    
    with st.container():
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            # Make URL clickable
            st.markdown(f"{indent}**{icon} [{link.get('link_type', 'SharePoint Link')}]({link['url']})**")
            if link.get('description'):
                st.write(f"{indent}{link['description']}")
            st.caption(f"{indent}Added by {link.get('created_by', 'Unknown')} on {link.get('created_at', datetime.now()).strftime('%Y-%m-%d')}")
        
        with col2:
            st.write(f"**Access:** {access_icon} {link.get('access_level', 'Team Access')}")
            # Copy URL button
            if st.button("📋 Copy URL", key=f"copy_{link_id}"):
                st.code(link['url'])
                st.success("URL copied to display above!")
        
        with col3:
            if can_edit and (st.session_state.user_role in ['Admin', 'Partner'] or 
                           link.get('created_by') == st.session_state.current_user):
                if st.button("🗑️ Delete", key=f"delete_link_{link_id}"):
                    if delete_sharepoint_link(link_id):
                        if link_id in st.session_state.data.get('sharepoint_links', {}):
                            del st.session_state.data['sharepoint_links'][link_id]
                        st.success("SharePoint link deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete link.")
        
        if not is_subtask:
            st.markdown("---")

def validate_sharepoint_url(url):
    """Validate if the URL is a proper SharePoint URL"""
    sharepoint_patterns = [
        r'https://.*\.sharepoint\.com/.*',
        r'https://.*\.sharepoint-df\.com/.*',
        r'https://.*office\.com/.*'
    ]
    
    return any(re.match(pattern, url, re.IGNORECASE) for pattern in sharepoint_patterns)

# Database functions (add these to your database.py file)
def save_sharepoint_link(link_id: str, link_data: dict):
    """Save a SharePoint link to Supabase"""
    try:
        from database import init_supabase
        supabase = init_supabase()
        
        db_data = {
            'id': link_id,
            'problem_file_id': link_data['problem_file_id'],
            'entity_type': link_data['entity_type'],
            'entity_id': link_data['entity_id'],
            'url': link_data['url'],
            'description': link_data.get('description', ''),
            'link_type': link_data['link_type'],
            'access_level': link_data['access_level'],
            'created_by': link_data['created_by'],
            'created_at': link_data['created_at'].isoformat()
        }
        
        supabase.table('sharepoint_links').upsert(db_data).execute()
        return True
        
    except Exception as e:
        st.error(f"Error saving SharePoint link: {e}")
        return False

def delete_sharepoint_link(link_id: str):
    """Delete a SharePoint link from Supabase"""
    try:
        from database import init_supabase
        supabase = init_supabase()
        supabase.table('sharepoint_links').delete().eq('id', link_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting SharePoint link: {e}")
        return False

def load_sharepoint_links():
    """Load SharePoint links from Supabase (add this to your database.py load_data function)"""
    try:
        from database import init_supabase, safe_parse_date
        supabase = init_supabase()
        links_response = supabase.table('sharepoint_links').select('*').execute()
        
        links = {}
        for link in links_response.data:
            link_id = link['id']
            links[link_id] = {
                'problem_file_id': link['problem_file_id'],
                'entity_type': link['entity_type'],
                'entity_id': link['entity_id'],
                'url': link['url'],
                'description': link.get('description', ''),
                'link_type': link['link_type'],
                'access_level': link['access_level'],
                'created_by': link['created_by'],
                'created_at': safe_parse_date(link['created_at'])
            }
        
        st.session_state.data['sharepoint_links'] = links
        
    except Exception as e:
        st.error(f"Error loading SharePoint links: {e}")
        st.session_state.data['sharepoint_links'] = {}