"""
Executive summary page module
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from utils import get_accessible_files, calculate_project_progress

def show_executive_summary():
    """Display executive summary page"""
    st.title("📊 Executive Summary")
    
    accessible_files = get_accessible_files()
    
    if not accessible_files:
        st.info("No problem files to summarize.")
        return
    
    # Summary metrics
    total_files = len(accessible_files)
    overdue_count = 0
    completed_count = 0
    total_comments = 0
    total_contacts = 0
    
    summary_data = []
    
    for file_id, file_data in accessible_files.items():
        progress = calculate_project_progress(file_data['tasks'])
        
        # Count overdue tasks
        overdue_tasks = []
        for task_id, task in file_data['tasks'].items():
            for subtask_id, subtask in task['subtasks'].items():
                if (subtask['projected_end_date'].date() < datetime.now().date() and 
                    subtask['progress'] < 100):
                    overdue_tasks.append(f"{task['name']} - {subtask['name']}")
        
        if overdue_tasks:
            overdue_count += 1
        
        if progress >= 100:
            completed_count += 1
        
        # Count comments and contacts
        file_comments = 0
        for task_id in file_data['tasks']:
            file_comments += len([c for c in st.session_state.data.get('comments', {}).values() 
                                if c['entity_type'] == 'task' and c['entity_id'] == task_id])
            for subtask_id in file_data['tasks'][task_id]['subtasks']:
                file_comments += len([c for c in st.session_state.data.get('comments', {}).values() 
                                    if c['entity_type'] == 'subtask' and c['entity_id'] == subtask_id])
        
        file_contacts = len([c for c in st.session_state.data.get('contacts', {}).values() 
                           if c['problem_file_id'] == file_id])
        
        total_comments += file_comments
        total_contacts += file_contacts
        
        summary_data.append({
            'Problem File': file_data['problem_name'],
            'Owner': file_data['owner'],
            'Progress': f"{progress:.1f}%",
            'Overdue Tasks': len(overdue_tasks),
            'Comments': file_comments,
            'Contacts': file_contacts,
            'Status': '✅ Complete' if progress >= 100 else '🔴 Overdue' if overdue_tasks else '🟡 In Progress',
            'Last Modified': file_data.get('last_modified', datetime.now()).strftime('%Y-%m-%d %H:%M') if hasattr(file_data.get('last_modified', datetime.now()), 'strftime') else str(file_data.get('last_modified', 'N/A'))
        })
    
    # Key metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Total Projects", total_files)
    with col2:
        st.metric("Completed", completed_count)
    with col3:
        st.metric("With Overdue", overdue_count)
    with col4:
        st.metric("On Track", total_files - overdue_count - completed_count)
    with col5:
        st.metric("Total Comments", total_comments)
    with col6:
        st.metric("Total Contacts", total_contacts)
    
    # Summary table
    st.subheader("Project Overview")
    df_summary = pd.DataFrame(summary_data)
    st.dataframe(df_summary, use_container_width=True)
    
    # Progress chart
    st.subheader("Progress Distribution")
    progress_values = [float(row['Progress'].replace('%', '')) for row in summary_data]
    
    fig = px.histogram(
        x=progress_values,
        nbins=10,
        title="Project Progress Distribution",
        labels={'x': 'Progress (%)', 'y': 'Number of Projects'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed overdue tasks
    st.subheader("🚨 Overdue Tasks Details")
    overdue_details = []
    
    for file_id, file_data in accessible_files.items():
        for task_id, task in file_data['tasks'].items():
            for subtask_id, subtask in task['subtasks'].items():
                if (subtask['projected_end_date'].date() < datetime.now().date() and 
                    subtask['progress'] < 100):
                    # Only show if user has access to this task
                    if (st.session_state.user_role in ['Admin', 'Partner'] or 
                        file_data['owner'] == st.session_state.current_user or 
                        subtask['assigned_to'] == st.session_state.current_user):
                        days_overdue = (datetime.now().date() - subtask['projected_end_date'].date()).days
                        overdue_details.append({
                            'Project': file_data['problem_name'],
                            'Task': f"{task['name']} - {subtask['name']}",
                            'Assigned To': subtask['assigned_to'],
                            'Days Overdue': days_overdue,
                            'Progress': f"{subtask['progress']}%",
                            'Original Due Date': subtask['projected_end_date'].strftime('%Y-%m-%d')
                        })
    
    if overdue_details:
        df_overdue = pd.DataFrame(overdue_details)
        df_overdue = df_overdue.sort_values('Days Overdue', ascending=False)
        st.dataframe(df_overdue, use_container_width=True)
    else:
        st.success("🎉 No overdue tasks!")
    
    # Partner Activity Summary (if user is admin or partner)
    if st.session_state.user_role in ['Admin', 'Partner']:
        st.subheader("🤝 Partner Activity Summary")
        
        partner_activity = {}
        for comment in st.session_state.data.get('comments', {}).values():
            if comment.get('user_role') == 'Partner':
                user = comment['user_name']
                if user not in partner_activity:
                    partner_activity[user] = {'comments': 0, 'files_engaged': set()}
                partner_activity[user]['comments'] += 1
                
                # Find which file this comment belongs to
                for file_id, file_data in accessible_files.items():
                    if comment['entity_type'] == 'task' and comment['entity_id'] in file_data['tasks']:
                        partner_activity[user]['files_engaged'].add(file_id)
                    elif comment['entity_type'] == 'subtask':
                        for task in file_data['tasks'].values():
                            if comment['entity_id'] in task['subtasks']:
                                partner_activity[user]['files_engaged'].add(file_id)
        
        if partner_activity:
            partner_data = []
            for partner, data in partner_activity.items():
                partner_data.append({
                    'Partner': partner,
                    'Total Comments': data['comments'],
                    'Files Engaged': len(data['files_engaged'])
                })
            
            df_partners = pd.DataFrame(partner_data)
            st.dataframe(df_partners, use_container_width=True)
        else:
            st.info("No partner activity recorded yet.")