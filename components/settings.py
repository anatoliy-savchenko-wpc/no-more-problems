"""
File settings component with email status and timeline management
"""
import streamlit as st
from datetime import datetime, timedelta
from database import save_problem_file

def is_email_configured():
    """Check if email is properly configured"""
    try:
        # Import here to avoid circular dependency
        from email_handler import is_email_configured as check_email
        return check_email()
    except:
        return False

def show_file_settings(file_id, problem_file, can_edit):
    """Display file settings tab with timeline management"""
    st.subheader("⚙️ File Settings")
    
    # Show email configuration status
    if is_email_configured():
        st.success("📧 Email notifications are configured and active")
    else:
        st.warning("📧 Email notifications are not configured. Add SendGrid API key in secrets.")
    
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
                
                # Get current end date or default to 30 days from start
                current_end_date = problem_file.get('project_end_date')
                if current_end_date is None:
                    current_end_date = problem_file['project_start_date'] + timedelta(days=30)
                
                new_end_date = st.date_input("Project End Date",
                                           value=current_end_date.date(),
                                           min_value=new_start_date)
                new_display_week = st.number_input("Display Week", 
                                                 value=problem_file['display_week'], min_value=1)
            
            # Show duration
            duration = (new_end_date - new_start_date).days
            st.info(f"📅 Project Duration: {duration} days")
            
            # Check if any tasks would fall outside new boundaries
            tasks_outside = []
            for task in problem_file.get('tasks', {}).values():
                for subtask in task.get('subtasks', {}).values():
                    if (subtask['start_date'].date() < new_start_date or 
                        subtask['projected_end_date'].date() > new_end_date):
                        tasks_outside.append(f"{task['name']} - {subtask['name']}")
            
            if tasks_outside:
                st.error("⚠️ The following tasks would fall outside the new project dates:")
                for task_name in tasks_outside[:5]:  # Show first 5
                    st.write(f"  • {task_name}")
                if len(tasks_outside) > 5:
                    st.write(f"  ... and {len(tasks_outside) - 5} more")
                st.warning("Please adjust task dates before changing project boundaries.")
            
            if st.form_submit_button("Update Settings"):
                if tasks_outside:
                    st.error("Cannot update: Some tasks are outside the new project boundaries!")
                else:
                    problem_file['problem_name'] = new_name
                    problem_file['owner'] = new_owner
                    problem_file['project_start_date'] = datetime.combine(new_start_date, datetime.min.time())
                    problem_file['project_end_date'] = datetime.combine(new_end_date, datetime.min.time())
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
            # Handle missing project_end_date
            end_date = problem_file.get('project_end_date', problem_file['project_start_date'] + timedelta(days=30))
            
            st.write(f"**Project Start Date:** {problem_file['project_start_date'].strftime('%Y-%m-%d')}")
            st.write(f"**Project End Date:** {end_date.strftime('%Y-%m-%d')}")
            st.write(f"**Display Week:** {problem_file['display_week']}")
            
            duration = (end_date - problem_file['project_start_date']).days
            st.write(f"**Duration:** {duration} days")
    
    # File information (always visible)
    st.subheader("📋 File Information")
    col1, col2 = st.columns(2)
    with col1:
        created_date = problem_file.get('created_date', 'Unknown')
        if hasattr(created_date, 'strftime'):
            created_str = created_date.strftime('%Y-%m-%d %H:%M')
        else:
            created_str = str(created_date)
        st.write(f"**Created:** {created_str}")
        st.write(f"**Total Tasks:** {len(problem_file.get('tasks', {}))}")
        
        # Count total comments
        total_comments = 0
        for task_id in problem_file.get('tasks', {}):
            total_comments += len([c for c in st.session_state.data.get('comments', {}).values() 
                                 if c['entity_type'] == 'task' and c['entity_id'] == task_id])
            for subtask_id in problem_file.get('tasks', {}).get(task_id, {}).get('subtasks', {}):
                total_comments += len([c for c in st.session_state.data.get('comments', {}).values() 
                                     if c['entity_type'] == 'subtask' and c['entity_id'] == subtask_id])
        st.write(f"**Total Comments:** {total_comments}")
    
    with col2:
        last_modified = problem_file.get('last_modified', 'Unknown')
        if hasattr(last_modified, 'strftime'):
            modified_str = last_modified.strftime('%Y-%m-%d %H:%M')
        else:
            modified_str = str(last_modified)
        st.write(f"**Last Modified:** {modified_str}")
        
        total_subtasks = sum(len(task.get('subtasks', {})) for task in problem_file.get('tasks', {}).values())
        st.write(f"**Total Subtasks:** {total_subtasks}")
        
        # Count contacts
        contacts_count = len([c for c in st.session_state.data.get('contacts', {}).values() 
                            if c['problem_file_id'] == file_id])
        st.write(f"**Total Contacts:** {contacts_count}")