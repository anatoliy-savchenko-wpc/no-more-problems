"""
File settings component
"""
import streamlit as st
from datetime import datetime
from database import save_problem_file

def show_file_settings(file_id, problem_file, can_edit):
    """Display file settings tab"""
    st.subheader("⚙️ File Settings")
    
    if can_edit:
        with st.form("edit_metadata"):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("Problem Name", value=problem_file['problem_name'])
                # Only admin and partner can change owner
                if st.session_state.user_role in ['Admin', 'Partner']:
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
        
        # Count total comments
        total_comments = 0
        for task_id in problem_file['tasks']:
            total_comments += len([c for c in st.session_state.data.get('comments', {}).values() 
                                 if c['entity_type'] == 'task' and c['entity_id'] == task_id])
            for subtask_id in problem_file['tasks'][task_id]['subtasks']:
                total_comments += len([c for c in st.session_state.data.get('comments', {}).values() 
                                     if c['entity_type'] == 'subtask' and c['entity_id'] == subtask_id])
        st.write(f"**Total Comments:** {total_comments}")
    with col2:
        st.write(f"**Last Modified:** {problem_file.get('last_modified', 'Unknown').strftime('%Y-%m-%d %H:%M') if hasattr(problem_file.get('last_modified'), 'strftime') else 'Unknown'}")
        total_subtasks = sum(len(task['subtasks']) for task in problem_file['tasks'].values())
        st.write(f"**Total Subtasks:** {total_subtasks}")
        
        # Count contacts
        contacts_count = len([c for c in st.session_state.data.get('contacts', {}).values() 
                            if c['problem_file_id'] == file_id])
        st.write(f"**Total Contacts:** {contacts_count}")