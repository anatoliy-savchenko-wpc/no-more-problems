"""
Visualization components for Gantt charts and analytics
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

def create_gantt_chart(problem_file):
    """Create Gantt chart for problem file"""
    tasks_data = []
    
    for task_id, task in problem_file['tasks'].items():
        for subtask_id, subtask in task['subtasks'].items():
            # Determine color based on progress
            if subtask['progress'] == 100:
                color = 'green'
            elif subtask['progress'] > 0:
                color = 'orange'
            else:
                color = 'red'
            
            # Check if overdue
            is_overdue = (subtask['projected_end_date'].date() < datetime.now().date() and 
                         subtask['progress'] < 100)
            
            tasks_data.append({
                'Task': f"{task['name']} - {subtask['name']}",
                'Start': subtask['start_date'],
                'Finish': subtask['projected_end_date'],
                'Progress': subtask['progress'],
                'Assigned To': subtask['assigned_to'],
                'Color': color,
                'Overdue': is_overdue
            })
    
    if not tasks_data:
        return None
    
    df = pd.DataFrame(tasks_data)
    
    fig = px.timeline(
        df, 
        x_start="Start", 
        x_end="Finish", 
        y="Task",
        color='Color',
        hover_data=['Progress', 'Assigned To', 'Overdue'],
        title=f"Gantt Chart - {problem_file['problem_name']}"
    )
    
    fig.update_layout(
        height=max(400, len(tasks_data) * 30),
        xaxis_title="Timeline",
        yaxis_title="Tasks"
    )
    
    return fig

def show_gantt_chart_tab(problem_file):
    """Display Gantt chart tab"""
    st.subheader("📈 Project Timeline")
    
    gantt_fig = create_gantt_chart(problem_file)
    if gantt_fig:
        st.plotly_chart(gantt_fig, use_container_width=True)
        
        # Timeline insights
        st.subheader("📊 Timeline Insights")
        
        # Calculate project duration and other metrics
        all_dates = []
        overdue_count = 0
        completed_count = 0
        
        for task in problem_file['tasks'].values():
            for subtask in task['subtasks'].values():
                all_dates.extend([subtask['start_date'], subtask['projected_end_date']])
                if subtask['progress'] == 100:
                    completed_count += 1
                elif subtask['projected_end_date'].date() < datetime.now().date() and subtask['progress'] < 100:
                    overdue_count += 1
        
        if all_dates:
            project_start = min(all_dates)
            project_end = max(all_dates)
            duration_days = (project_end - project_start).days
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Project Duration", f"{duration_days} days")
            with col2:
                st.metric("Completed Subtasks", completed_count)
            with col3:
                st.metric("Overdue Subtasks", overdue_count)
            with col4:
                st.metric("Project End Date", project_end.strftime('%Y-%m-%d'))
    else:
        st.info("No tasks to display in Gantt chart. Add some subtasks first!")

def show_file_analytics(problem_file):
    """Display file analytics tab"""
    st.subheader("📊 Project Analytics")
    
    if not problem_file['tasks']:
        st.info("No tasks available for analytics.")
        return
    
    # Collect analytics data
    user_workload = {}
    progress_data = []
    status_data = {'Completed': 0, 'In Progress': 0, 'Not Started': 0, 'Overdue': 0}
    
    for task in problem_file['tasks'].values():
        for subtask in task['subtasks'].values():
            # User workload
            user = subtask['assigned_to']
            if user not in user_workload:
                user_workload[user] = {'total': 0, 'completed': 0, 'overdue': 0}
            user_workload[user]['total'] += 1
            
            # Progress tracking
            progress_data.append(subtask['progress'])
            
            # Status tracking
            if subtask['progress'] == 100:
                status_data['Completed'] += 1
                user_workload[user]['completed'] += 1
            elif subtask['progress'] > 0:
                status_data['In Progress'] += 1
            else:
                status_data['Not Started'] += 1
            
            # Check if overdue
            if (subtask['projected_end_date'].date() < datetime.now().date() and 
                subtask['progress'] < 100):
                status_data['Overdue'] += 1
                user_workload[user]['overdue'] += 1
    
    # Display charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Progress distribution
        if progress_data:
            fig_progress = px.histogram(
                x=progress_data,
                nbins=10,
                title="Progress Distribution",
                labels={'x': 'Progress (%)', 'y': 'Number of Subtasks'}
            )
            st.plotly_chart(fig_progress, use_container_width=True)
    
    with col2:
        # Status pie chart
        fig_status = px.pie(
            values=list(status_data.values()),
            names=list(status_data.keys()),
            title="Task Status Distribution"
        )
        st.plotly_chart(fig_status, use_container_width=True)
    
    # User workload analysis
    if user_workload:
        st.subheader("👥 Team Workload Analysis")
        
        workload_data = []
        for user, data in user_workload.items():
            completion_rate = (data['completed'] / data['total'] * 100) if data['total'] > 0 else 0
            workload_data.append({
                'User': user,
                'Total Tasks': data['total'],
                'Completed': data['completed'],
                'Overdue': data['overdue'],
                'Completion Rate': f"{completion_rate:.1f}%"
            })
        
        df_workload = pd.DataFrame(workload_data)
        st.dataframe(df_workload, use_container_width=True)
    
    # Comments activity analysis
    st.subheader("💬 Comments Activity")
    
    comments_by_user = {}
    for comment in st.session_state.data.get('comments', {}).values():
        user = comment.get('user_name', comment.get('user', 'Unknown'))
        if user not in comments_by_user:
            comments_by_user[user] = {'total': 0, 'as_partner': 0, 'as_admin': 0, 'as_user': 0}
        comments_by_user[user]['total'] += 1
        role = comment.get('user_role', 'User')
        if role == 'Partner':
            comments_by_user[user]['as_partner'] += 1
        elif role == 'Admin':
            comments_by_user[user]['as_admin'] += 1
        else:
            comments_by_user[user]['as_user'] += 1
    
    if comments_by_user:
        comments_data = []
        for user, data in comments_by_user.items():
            comments_data.append({
                'User': user,
                'Total Comments': data['total'],
                'As Partner': data['as_partner'],
                'As Admin': data['as_admin'],
                'As User': data['as_user']
            })
        
        df_comments = pd.DataFrame(comments_data)
        st.dataframe(df_comments, use_container_width=True)
    else:
        st.info("No comments activity yet.")