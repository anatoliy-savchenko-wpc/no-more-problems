"""
Task management component - Clean Version
"""
import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, timedelta
from database import save_task, save_subtask, delete_task, delete_subtask
from utils import calculate_task_progress, can_delete_items
from components.comments import show_comments_section

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
            
            # Comments section for task
            with st.expander(f"💬 Task Comments"):
                show_comments_section('task', task_id, task['name'])
            
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
    
    # Select subtask for editing or viewing comments
    subtask_to_manage = st.selectbox(
        f"Select subtask to manage:",
        options=[None] + list(task['subtasks'].keys()),
        format_func=lambda x: "Select..." if x is None else task['subtasks'][x]['name'],
        key=f"manage_select_{task_id}"
    )
    
    if subtask_to_manage:
        subtask = task['subtasks'][subtask_to_manage]
        
        # Create tabs for edit and comments
        subtask_tabs = st.tabs(["✏️ Edit Details", "💬 Comments"])
        
        with subtask_tabs[0]:
            show_edit_subtask_form(task_id, subtask_to_manage, task, problem_file, can_edit)
        
        with subtask_tabs[1]:
            show_comments_section('subtask', subtask_to_manage, subtask['name'])

def show_edit_subtask_form(task_id, subtask_id, task, problem_file, can_edit_param):
    """Display edit subtask form"""
    subtask = task['subtasks'][subtask_id]
    
    # Check if user can edit this specific subtask
    can_edit_subtask = (st.session_state.user_role in ['Admin', 'Partner'] or 
                       problem_file['owner'] == st.session_state.current_user or
                       subtask['assigned_to'] == st.session_state.current_user)
    
    if not can_edit_subtask:
        st.info("You can only edit subtasks assigned to you or if you're an admin/partner.")
        return
    
    with st.form(f"edit_subtask_{task_id}_{subtask_id}"):
        st.write(f"**Editing: {subtask['name']}**")
        ecol1, ecol2, ecol3 = st.columns(3)
        with ecol1:
            new_subtask_name = st.text_input("Subtask Name", value=subtask['name'])
            # Only admin, partner and owner can reassign tasks
            if st.session_state.user_role in ['Admin', 'Partner'] or problem_file['owner'] == st.session_state.current_user:
                new_assigned_to = st.selectbox("Assigned To", st.session_state.data['users'],
                                             index=st.session_state.data['users'].index(subtask['assigned_to']))
            else:
                new_assigned_to = subtask['assigned_to']
                st.write(f"**Assigned To:** {new_assigned_to}")
        with ecol2:
            new_start_date = st.date_input("Start Date", value=subtask['start_date'].date())
            new_progress = st.slider("Progress %", 0, 100, subtask['progress'])
        with ecol3:
            new_end_date = st.date_input("Projected End Date", 
                                       value=subtask['projected_end_date'].date())
            new_notes = st.text_area("Notes", value=subtask['notes'])
        
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