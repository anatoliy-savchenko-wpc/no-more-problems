"""
Visualization components for enhanced Gantt charts and analytics
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

def create_gantt_chart(problem_file):
    """Create enhanced Gantt chart with boundaries and visual improvements"""
    tasks_data = []
    
    # Get project dates with fallbacks
    project_start = problem_file.get('project_start_date', datetime.now())
    project_end = problem_file.get('project_end_date')
    
    # Ensure we have valid dates
    if not project_end:
        project_end = project_start + timedelta(days=30)
    
    # Convert to datetime if needed
    if not isinstance(project_start, datetime):
        project_start = datetime.now()
    if not isinstance(project_end, datetime):
        project_end = project_start + timedelta(days=30)
    
    for task_id, task in problem_file.get('tasks', {}).items():
        for subtask_id, subtask in task.get('subtasks', {}).items():
            # Determine color based on progress and status
            is_overdue = (subtask['projected_end_date'].date() < datetime.now().date() and 
                         subtask['progress'] < 100)
            
            # Check if within project bounds
            within_bounds = (project_start.date() <= subtask['start_date'].date() <= project_end.date() and
                           project_start.date() <= subtask['projected_end_date'].date() <= project_end.date())
            
            if subtask['progress'] == 100:
                color = '#28a745'  # Green for completed
            elif is_overdue:
                color = '#dc3545'  # Red for overdue
            elif subtask['progress'] > 0:
                color = '#ffc107'  # Yellow for in progress
            else:
                color = '#6c757d'  # Gray for not started
            
            tasks_data.append({
                'Task': f"{task['name']}<br>{subtask['name']}",
                'Start': subtask['start_date'],
                'Finish': subtask['projected_end_date'],
                'Progress': subtask['progress'],
                'Assigned To': subtask['assigned_to'],
                'Color': color,
                'Status': 'Overdue' if is_overdue else 'Complete' if subtask['progress'] == 100 else 'In Progress' if subtask['progress'] > 0 else 'Not Started',
                'Within Bounds': '✅' if within_bounds else '⚠️'
            })
    
    if not tasks_data:
        return None
    
    df = pd.DataFrame(tasks_data)
    
    # Create figure
    fig = go.Figure()
    
    # Add tasks as horizontal bars
    for i, row in df.iterrows():
        fig.add_trace(go.Scatter(
            x=[row['Start'], row['Finish']],
            y=[row['Task'], row['Task']],
            mode='lines',
            line=dict(color=row['Color'], width=20),
            hovertemplate=(
                f"<b>{row['Task']}</b><br>" +
                f"Progress: {row['Progress']}%<br>" +
                f"Assigned: {row['Assigned To']}<br>" +
                f"Status: {row['Status']}<br>" +
                f"Within Bounds: {row['Within Bounds']}<br>" +
                f"Start: %{{x[0]|%Y-%m-%d}}<br>" +
                f"End: %{{x[1]|%Y-%m-%d}}<extra></extra>"
            ),
            showlegend=False
        ))
    
    # Add project boundaries as shapes instead of vlines to avoid the error
    fig.add_shape(
        type="line",
        x0=project_start, x1=project_start,
        y0=0, y1=1,
        xref="x", yref="paper",
        line=dict(color="blue", width=2, dash="dash")
    )
    
    fig.add_shape(
        type="line",
        x0=project_end, x1=project_end,
        y0=0, y1=1,
        xref="x", yref="paper",
        line=dict(color="blue", width=2, dash="dash")
    )
    
    # Add today's date line
    fig.add_shape(
        type="line",
        x0=datetime.now(), x1=datetime.now(),
        y0=0, y1=1,
        xref="x", yref="paper",
        line=dict(color="red", width=2)
    )
    
    # Add annotations for the lines
    fig.add_annotation(
        x=project_start, y=1.02,
        text="Project Start",
        showarrow=False,
        xref="x", yref="paper",
        font=dict(size=10, color="blue")
    )
    
    fig.add_annotation(
        x=project_end, y=1.02,
        text="Project End",
        showarrow=False,
        xref="x", yref="paper",
        font=dict(size=10, color="blue")
    )
    
    fig.add_annotation(
        x=datetime.now(), y=-0.02,
        text="Today",
        showarrow=False,
        xref="x", yref="paper",
        font=dict(size=10, color="red")
    )
    
    # Calculate date range for x-axis
    date_buffer = timedelta(days=7)
    x_min = project_start - date_buffer
    x_max = project_end + date_buffer
    
    # Update layout
    fig.update_layout(
        title=dict(
            text=f"📊 Gantt Chart - {problem_file['problem_name']}",
            font=dict(size=20)
        ),
        xaxis=dict(
            title="Timeline",
            type='date',
            range=[x_min, x_max],
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)'
        ),
        yaxis=dict(
            title="Tasks",
            autorange='reversed',
            showgrid=False
        ),
        height=max(400, len(tasks_data) * 60),
        hovermode='closest',
        plot_bgcolor='white',
        margin=dict(l=200, r=50, t=80, b=50)
    )
    
    # Add legend
    legend_items = [
        ('Complete', '#28a745'),
        ('In Progress', '#ffc107'),
        ('Not Started', '#6c757d'),
        ('Overdue', '#dc3545')
    ]
    
    for i, (label, color) in enumerate(legend_items):
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode='markers',
            marker=dict(size=10, color=color),
            showlegend=True,
            name=label
        ))
    
    return fig

def show_gantt_chart_tab(problem_file):
    """Display Gantt chart tab"""
    st.subheader("📈 Project Timeline")
    
    # Ensure project has end date
    if 'project_end_date' not in problem_file or problem_file['project_end_date'] is None:
        problem_file['project_end_date'] = problem_file.get('project_start_date', datetime.now()) + timedelta(days=30)
    
    gantt_fig = create_gantt_chart(problem_file)
    if gantt_fig:
        st.plotly_chart(gantt_fig, use_container_width=True)
        
        # Timeline insights
        st.subheader("📊 Timeline Insights")
        
        # Calculate project duration and other metrics
        all_dates = []
        overdue_count = 0
        completed_count = 0
        
        for task in problem_file.get('tasks', {}).values():
            for subtask in task.get('subtasks', {}).values():
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
    
    if not problem_file.get('tasks'):
        st.info("No tasks available for analytics.")
        return
    
    # Collect analytics data
    user_workload = {}
    progress_data = []
    status_data = {'Completed': 0, 'In Progress': 0, 'Not Started': 0, 'Overdue': 0}
    
    for task in problem_file.get('tasks', {}).values():
        for subtask in task.get('subtasks', {}).values():
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