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
from components.event_log import show_event_log_section
from components.sharepoint_links import show_sharepoint_links_section

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
                        # Add ID field for analytics
                        file_data['id'] = file_id
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
    
    # Enhanced summary cards with new data types
    col1, col2, col3, col4, col5 = st.columns(5)
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
    with col5:
        # Count total events across all accessible files
        total_events = len([e for e in st.session_state.data.get('event_logs', {}).values() 
                           if e['problem_file_id'] in accessible_files.keys()])
        st.metric("Total Events", total_events)
    
    # Files table with enhanced data
    st.subheader("Problem Files Overview")
    
    files_data = []
    for file_id, file_data in accessible_files.items():
        progress = calculate_project_progress(file_data['tasks'])
        
        # Count comments (improved logic for file-level comments)
        comments_count = len([c for c in st.session_state.data.get('comments', {}).values() 
                            if c.get('entity_id') == file_id])
        
        # Count contacts
        contacts_count = len([c for c in st.session_state.data.get('contacts', {}).values() 
                            if c['problem_file_id'] == file_id])
        
        # Count events
        events_count = len([e for e in st.session_state.data.get('event_logs', {}).values() 
                          if e['problem_file_id'] == file_id])
        
        # Count SharePoint links
        links_count = len([l for l in st.session_state.data.get('sharepoint_links', {}).values() 
                         if l['problem_file_id'] == file_id])
        
        files_data.append({
            'ID': file_id,
            'Name': file_data['problem_name'],
            'Owner': file_data['owner'],
            'Progress': f"{progress:.1f}%",
            'Comments': comments_count,
            'Contacts': contacts_count,
            'Events': events_count,
            'SharePoint Links': links_count,
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

        # Enhanced action buttons
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

        # Show quick preview of selected file
        st.subheader(f"📋 Quick Preview: {selected_file_data['problem_name']}")
        
        preview_col1, preview_col2 = st.columns(2)
        
        with preview_col1:
            st.write("**Recent Activity:**")
            # Show recent events for this file
            file_events = [(e['created_at'], e['title']) for e in st.session_state.data.get('event_logs', {}).values() 
                          if e['problem_file_id'] == selected_file_id]
            file_events.sort(reverse=True)
            
            if file_events:
                for event_date, event_title in file_events[:3]:  # Show last 3 events
                    st.write(f"• {event_title} ({event_date.strftime('%m/%d')})")
            else:
                st.write("No recent events")
        
        with preview_col2:
            st.write("**Key Resources:**")
            # Show SharePoint links count by type
            file_links = [l for l in st.session_state.data.get('sharepoint_links', {}).values() 
                         if l['problem_file_id'] == selected_file_id]
            
            if file_links:
                link_types = {}
                for link in file_links:
                    link_type = link['link_type']
                    link_types[link_type] = link_types.get(link_type, 0) + 1
                
                for link_type, count in link_types.items():
                    st.write(f"• {link_type}: {count}")
            else:
                st.write("No SharePoint links")
        
        # Handle file deletion confirmation
        if hasattr(st.session_state, 'file_to_delete') and st.session_state.file_to_delete:
            file_to_delete = st.session_state.file_to_delete
            file_name = accessible_files[file_to_delete]['problem_name']
            
            st.error(f"⚠️ **Confirm Deletion of '{file_name}'**")
            st.warning("This action cannot be undone. All tasks, subtasks, comments, contacts, events, and SharePoint links will be permanently deleted.")
            
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
    
    # Enhanced quick info bar with new metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
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
    with col6:
        events_count = len([e for e in st.session_state.data.get('event_logs', {}).values() 
                          if e['problem_file_id'] == file_id])
        st.metric("Events", events_count)
    
    # Check permissions
    can_edit = can_edit_file(problem_file['owner'])
    
    if not can_edit and st.session_state.user_role != 'Partner':
        st.info("👁️ **View Only Mode** - You can view this file but cannot make changes. Contact the owner or a partner for edit access.")
    
    # Check for overdue tasks and update (only if can edit)
    if can_edit and check_overdue_and_update(problem_file):
        st.warning("Some overdue tasks have been automatically updated with new deadlines.")
    
    # Enhanced navigation tabs with new components
    tabs = st.tabs([
        "📋 Tasks & Subtasks", 
        "📊 Gantt Chart", 
        "📅 Event Log",
        "🔗 SharePoint Links",
        "📇 Contacts", 
        "📝 File Settings", 
        "📈 Analytics"
    ])
    
    with tabs[0]:
        show_task_management(file_id, problem_file, can_edit)
    
    with tabs[1]:
        show_gantt_chart_tab(problem_file)
    
    with tabs[2]:
        show_event_log_section(file_id, problem_file, can_edit)
    
    with tabs[3]:
        show_sharepoint_links_section(file_id, problem_file, can_edit)
    
    with tabs[4]:
        show_contacts_section(file_id, problem_file)
    
    with tabs[5]:
        show_file_settings(file_id, problem_file, can_edit)
    
    with tabs[6]:
        show_file_analytics(problem_file)

def show_project_dashboard():
    """Enhanced dashboard showing overview of all projects with new data types"""
    st.title("🎯 Project Dashboard")
    
    accessible_files = get_accessible_files()
    
    if not accessible_files:
        st.info("No problem files available.")
        if st.button("➕ Create Your First Problem File"):
            st.session_state.page = "Create Problem File"
            st.rerun()
        return
    
    # Enhanced overview metrics
    st.subheader("📊 Overview Metrics")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("Total Projects", len(accessible_files))
    
    with col2:
        completed_projects = len([f for f in accessible_files.values() 
                                if calculate_project_progress(f['tasks']) >= 100])
        st.metric("Completed Projects", completed_projects)
    
    with col3:
        total_subtasks = sum(sum(len(task['subtasks']) for task in file_data['tasks'].values()) 
                           for file_data in accessible_files.values())
        st.metric("Total Subtasks", total_subtasks)
    
    with col4:
        total_events = len([e for e in st.session_state.data.get('event_logs', {}).values() 
                           if e['problem_file_id'] in accessible_files.keys()])
        st.metric("Total Events", total_events)
    
    with col5:
        total_links = len([l for l in st.session_state.data.get('sharepoint_links', {}).values() 
                         if l['problem_file_id'] in accessible_files.keys()])
        st.metric("SharePoint Links", total_links)
    
    with col6:
        resolved_comments = len([c for c in st.session_state.data.get('comments', {}).values() 
                               if c.get('resolved', False) and c.get('entity_id') in accessible_files.keys()])
        st.metric("Resolved Comments", resolved_comments)
    
    # Recent activity across all projects
    st.subheader("🕒 Recent Activity")
    
    # Combine recent events and comments
    recent_activity = []
    
    # Add recent events
    for event in st.session_state.data.get('event_logs', {}).values():
        if event['problem_file_id'] in accessible_files:
            project_name = accessible_files[event['problem_file_id']]['problem_name']
            recent_activity.append({
                'timestamp': event['created_at'],
                'type': 'Event',
                'description': f"📅 {event['title']} in {project_name}",
                'project': project_name
            })
    
    # Add recent comments
    for comment in st.session_state.data.get('comments', {}).values():
        if comment.get('entity_id') in accessible_files:
            project_name = accessible_files[comment['entity_id']]['problem_name']
            status = "✅ Resolved" if comment.get('resolved') else "💬 New"
            recent_activity.append({
                'timestamp': comment['created_at'],
                'type': 'Comment',
                'description': f"{status} comment by {comment['user_name']} in {project_name}",
                'project': project_name
            })
    
    # Sort by timestamp and show recent items
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    
    if recent_activity:
        for activity in recent_activity[:10]:  # Show last 10 activities
            st.write(f"• {activity['description']} ({activity['timestamp'].strftime('%m/%d %H:%M')})")
    else:
        st.write("No recent activity")
    
    # Projects at risk (overdue or behind schedule)
    st.subheader("⚠️ Projects Requiring Attention")
    
    projects_at_risk = []
    for file_id, file_data in accessible_files.items():
        progress = calculate_project_progress(file_data['tasks'])
        
        # Check for overdue subtasks
        overdue_count = 0
        for task in file_data['tasks'].values():
            for subtask in task['subtasks'].values():
                if (subtask['projected_end_date'].date() < datetime.now().date() and 
                    subtask['progress'] < 100):
                    overdue_count += 1
        
        if overdue_count > 0 or progress < 50:
            projects_at_risk.append({
                'name': file_data['problem_name'],
                'progress': progress,
                'overdue_tasks': overdue_count,
                'owner': file_data['owner']
            })
    
    if projects_at_risk:
        risk_df = pd.DataFrame(projects_at_risk)
        st.dataframe(risk_df, use_container_width=True)
    else:
        st.success("✅ All projects are on track!")