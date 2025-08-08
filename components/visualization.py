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
    try:
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
        
        # Collect task data
        tasks_data = []
        for task_id, task in problem_file.get('tasks', {}).items():
            for subtask_id, subtask in task.get('subtasks', {}).items():
                # Determine status and color
                is_overdue = (subtask['projected_end_date'].date() < datetime.now().date() and 
                             subtask['progress'] < 100)
                
                within_bounds = (project_start.date() <= subtask['start_date'].date() <= project_end.date() and
                               project_start.date() <= subtask['projected_end_date'].date() <= project_end.date())
                
                if subtask['progress'] == 100:
                    color = 'Complete'
                elif is_overdue:
                    color = 'Overdue'
                elif subtask['progress'] > 0:
                    color = 'In Progress'
                else:
                    color = 'Not Started'
                
                tasks_data.append({
                    'Task': f"{task['name']} - {subtask['name']}",
                    'Start': subtask['start_date'].strftime('%Y-%m-%d'),
                    'Finish': subtask['projected_end_date'].strftime('%Y-%m-%d'),
                    'Resource': subtask['assigned_to'],
                    'Progress': subtask['progress'],
                    'Status': color,
                    'Within Bounds': 'Yes' if within_bounds else 'No'
                })
        
        if not tasks_data:
            return None
        
        # Create DataFrame
        df = pd.DataFrame(tasks_data)
        
        # Define color mapping
        color_map = {
            'Complete': '#28a745',
            'In Progress': '#ffc107',
            'Not Started': '#6c757d',
            'Overdue': '#dc3545'
        }
        
        # Create Gantt chart using plotly express
        fig = px.timeline(
            df,
            x_start='Start',
            x_end='Finish',
            y='Task',
            color='Status',
            color_discrete_map=color_map,
            hover_data=['Resource', 'Progress', 'Within Bounds'],
            title=f"Gantt Chart - {problem_file['problem_name']}"
        )
        
        # Update layout
        fig.update_layout(
            height=max(400, len(tasks_data) * 50),
            xaxis_title="Timeline",
            yaxis_title="Tasks",
            showlegend=True,
            hovermode='closest'
        )
        
        # Reverse y-axis to show tasks from top to bottom
        fig.update_yaxes(autorange="reversed")
        
        # Add reference lines as shapes (not vlines)
        # Project start line
        fig.add_shape(
            type="line",
            x0=project_start.strftime('%Y-%m-%d'),
            y0=0,
            x1=project_start.strftime('%Y-%m-%d'),
            y1=1,
            xref="x",
            yref="paper",
            line=dict(color="blue", width=2, dash="dash"),
        )
        
        # Project end line
        fig.add_shape(
            type="line",
            x0=project_end.strftime('%Y-%m-%d'),
            y0=0,
            x1=project_end.strftime('%Y-%m-%d'),
            y1=1,
            xref="x",
            yref="paper",
            line=dict(color="blue", width=2, dash="dash"),
        )
        
        # Today line
        fig.add_shape(
            type="line",
            x0=datetime.now().strftime('%Y-%m-%d'),
            y0=0,
            x1=datetime.now().strftime('%Y-%m-%d'),
            y1=1,
            xref="x",
            yref="paper",
            line=dict(color="red", width=2, dash="solid"),
        )
        
        # Add annotations for the reference lines
        fig.add_annotation(
            x=project_start.strftime('%Y-%m-%d'),
            y=1.05,
            text="Project Start",
            showarrow=False,
            xref="x",
            yref="paper",
            font=dict(size=10, color="blue"),
            xanchor="center"
        )
        
        fig.add_annotation(
            x=project_end.strftime('%Y-%m-%d'),
            y=1.05,
            text="Project End",
            showarrow=False,
            xref="x",
            yref="paper",
            font=dict(size=10, color="blue"),
            xanchor="center"
        )
        
        fig.add_annotation(
            x=datetime.now().strftime('%Y-%m-%d'),
            y=-0.05,
            text="Today",
            showarrow=False,
            xref="x",
            yref="paper",
            font=dict(size=10, color="red"),
            xanchor="center"
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Error creating Gantt chart: {str(e)}")
        return None

def show_gantt_chart_tab(problem_file):
    """Display Gantt chart tab"""
    st.subheader("📈 Project Timeline")
    
    # Ensure project has end date
    if 'project_end_date' not in problem_file or problem_file['project_end_date'] is None:
        project_start = problem_file.get('project_start_date', datetime.now())
        problem_file['project_end_date'] = project_start + timedelta(days=30)
    
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