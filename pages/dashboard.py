"""
Dashboard page module
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from utils import get_accessible_files, calculate_project_progress

def show_dashboard():
    """Display main dashboard"""
    st.title("📊 Problem File Tracker Dashboard")
    
    accessible_files = get_accessible_files()
    
    if not accessible_files:
        st.info("No problem files available. Create a new one or ask an admin/partner for access!")
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
                
                # Count comments and contacts for this file
                comments_count = 0
                for task in file_data['tasks'].values():
                    comments_count += len([c for c in st.session_state.data.get('comments', {}).values() 
                                         if c['entity_type'] == 'task' and c['entity_id'] in file_data['tasks']])
                    for subtask_id in task['subtasks']:
                        comments_count += len([c for c in st.session_state.data.get('comments', {}).values() 
                                             if c['entity_type'] == 'subtask' and c['entity_id'] == subtask_id])
                
                contacts_count = len([c for c in st.session_state.data.get('contacts', {}).values() 
                                    if c['problem_file_id'] == file_id])
                
                st.metric(
                    label=file_data['problem_name'],
                    value=f"{progress:.1f}%",
                    delta=f"💬 {comments_count} | 📇 {contacts_count}"
                )
                
                st.caption(ownership_indicator)
                
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
        
        # Recent Activity Section
        show_recent_activity(accessible_files)

def show_recent_activity(accessible_files):
    """Display recent activity including notes and comments"""
    st.subheader("📝 Recent Activity")
    
    tabs = st.tabs(["📝 Notes", "💬 Recent Comments", "📇 Recent Contacts"])
    
    with tabs[0]:
        # Recent Notes
        all_notes = []
        for file_id, file_data in accessible_files.items():
            for task_id, task in file_data['tasks'].items():
                for subtask_id, subtask in task['subtasks'].items():
                    if subtask.get('notes', '').strip():
                        # Only show notes for tasks assigned to user or if user is admin/partner/owner
                        if (st.session_state.user_role in ['Admin', 'Partner'] or 
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
            df_notes = pd.DataFrame(all_notes)
            st.dataframe(df_notes, use_container_width=True, height=400)
        else:
            st.info("No notes found. Add some notes to your tasks to see them here!")
    
    with tabs[1]:
        # Recent Comments
        recent_comments = []
        for comment_id, comment in st.session_state.data.get('comments', {}).items():
            # Check if comment belongs to an accessible file
            for file_id, file_data in accessible_files.items():
                if comment['entity_type'] == 'task' and comment['entity_id'] in file_data['tasks']:
                    recent_comments.append({
                        'Project': file_data['problem_name'],
                        'Task': file_data['tasks'][comment['entity_id']]['name'],
                        'User_Name': comment['user_name'],
                        'Role': comment.get('user_role', 'User'),
                        'Comment': comment['text'][:100] + '...' if len(comment['text']) > 100 else comment['text'],
                        'Posted': comment['created_at'].strftime('%Y-%m-%d %H:%M')
                    })
                elif comment['entity_type'] == 'subtask':
                    for task_id, task in file_data['tasks'].items():
                        if comment['entity_id'] in task['subtasks']:
                            recent_comments.append({
                                'Project': file_data['problem_name'],
                                'Task': f"{task['name']} - {task['subtasks'][comment['entity_id']]['name']}",
                                'User_Name': comment['user_name'],
                                'Role': comment.get('user_role', 'User'),
                                'Comment': comment['text'][:100] + '...' if len(comment['text']) > 100 else comment['text'],
                                'Posted': comment['created_at'].strftime('%Y-%m-%d %H:%M')
                            })
        
        if recent_comments:
            # Sort by date and take last 20
            recent_comments.sort(key=lambda x: x['Posted'], reverse=True)
            df_comments = pd.DataFrame(recent_comments[:20])
            st.dataframe(df_comments, use_container_width=True, height=400)
        else:
            st.info("No comments yet. Start a conversation on any task or subtask!")
    
    with tabs[2]:
        # Recent Contacts
        recent_contacts = []
        for contact_id, contact in st.session_state.data.get('contacts', {}).items():
            if contact['problem_file_id'] in accessible_files:
                recent_contacts.append({
                    'Project': accessible_files[contact['problem_file_id']]['problem_name'],
                    'Name': contact['name'],
                    'Organization': contact.get('organization', ''),
                    'Title': contact.get('title', ''),
                    'Email': contact.get('email', ''),
                    'Added By': contact.get('added_by', ''),
                    'Added On': contact['created_at'].strftime('%Y-%m-%d')
                })
        
        if recent_contacts:
            # Sort by date and take last 20
            recent_contacts.sort(key=lambda x: x['Added On'], reverse=True)
            df_contacts = pd.DataFrame(recent_contacts[:20])
            st.dataframe(df_contacts, use_container_width=True, height=400)
        else:
            st.info("No contacts added yet.")