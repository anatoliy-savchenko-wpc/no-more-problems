"""
Enhanced Visualization components with actual PDF export functionality
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import base64
from io import BytesIO
import plotly.io as pio
import re

# PDF generation imports
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF

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
        
        # Add reference lines as shapes
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

def analyze_comments_for_file(problem_file):
    """Analyze comments specifically for this problem file"""
    file_comments = {}
    resolved_comments = 0
    
    # Get all tasks and subtasks IDs for this file
    entity_ids = set()
    for task_id, task in problem_file.get('tasks', {}).items():
        entity_ids.add(task_id)
        for subtask_id in task.get('subtasks', {}).keys():
            entity_ids.add(subtask_id)
    
    # Filter comments for this file
    all_comments = st.session_state.data.get('comments', {})
    for comment_id, comment in all_comments.items():
        if comment.get('entity_id') in entity_ids:
            user = comment.get('user_name', comment.get('user', 'Unknown'))
            if user not in file_comments:
                file_comments[user] = {
                    'total': 0, 
                    'as_partner': 0, 
                    'as_admin': 0, 
                    'as_user': 0,
                    'resolved': 0,
                    'mentions_given': 0,
                    'mentions_received': 0
                }
            
            file_comments[user]['total'] += 1
            role = comment.get('user_role', 'User')
            
            if role == 'Partner':
                file_comments[user]['as_partner'] += 1
            elif role == 'Admin':
                file_comments[user]['as_admin'] += 1
            else:
                file_comments[user]['as_user'] += 1
            
            # Check if comment is marked as resolved
            if comment.get('resolved', False):
                file_comments[user]['resolved'] += 1
                resolved_comments += 1
            
            # Count mentions given (in this user's comments)
            comment_text = comment.get('text', '')
            mentions_in_comment = len(re.findall(r'@(\w+)', comment_text))
            file_comments[user]['mentions_given'] += mentions_in_comment
            
            # Count mentions received (this user mentioned by others)
            if f"@{user}" in comment_text and comment.get('user_name') != user:
                file_comments[user]['mentions_received'] += 1
    
    return file_comments, resolved_comments

def create_pdf_export_data(problem_file):
    """Create comprehensive data for PDF export"""
    try:
        # Project overview
        project_data = {
            'name': problem_file.get('problem_name', 'Unnamed Project'),
            'owner': problem_file.get('owner', 'Unknown'),
            'start_date': problem_file.get('project_start_date', datetime.now()).strftime('%Y-%m-%d'),
            'end_date': problem_file.get('project_end_date', datetime.now()).strftime('%Y-%m-%d'),
            'created': problem_file.get('created_date', datetime.now()).strftime('%Y-%m-%d'),
            'last_modified': problem_file.get('last_modified', datetime.now()).strftime('%Y-%m-%d')
        }
        
        # Task/Subtask summary
        total_tasks = len(problem_file.get('tasks', {}))
        total_subtasks = sum(len(task.get('subtasks', {})) for task in problem_file.get('tasks', {}).values())
        completed_subtasks = sum(1 for task in problem_file.get('tasks', {}).values() 
                               for subtask in task.get('subtasks', {}).values() 
                               if subtask.get('progress', 0) == 100)
        
        # Comments analysis
        file_comments, resolved_comments = analyze_comments_for_file(problem_file)
        total_comments = sum(data['total'] for data in file_comments.values())
        
        # Team workload
        user_workload = {}
        for task in problem_file.get('tasks', {}).values():
            for subtask in task.get('subtasks', {}).values():
                user = subtask['assigned_to']
                if user not in user_workload:
                    user_workload[user] = {'total': 0, 'completed': 0}
                user_workload[user]['total'] += 1
                if subtask['progress'] == 100:
                    user_workload[user]['completed'] += 1
        
        return {
            'project': project_data,
            'summary': {
                'total_tasks': total_tasks,
                'total_subtasks': total_subtasks,
                'completed_subtasks': completed_subtasks,
                'completion_rate': f"{(completed_subtasks/total_subtasks*100):.1f}%" if total_subtasks > 0 else "0%",
                'total_comments': total_comments,
                'resolved_comments': resolved_comments
            },
            'team_workload': user_workload,
            'comments_activity': file_comments
        }
    except Exception as e:
        st.error(f"Error creating export data: {e}")
        return None

def create_progress_bar_drawing(width, height, progress_percent, fill_color=colors.green):
    """Create a progress bar drawing for PDF"""
    drawing = Drawing(width, height)
    
    # Background bar
    drawing.add(Rect(0, 0, width, height, fillColor=colors.lightgrey, strokeColor=colors.grey))
    
    # Progress fill
    fill_width = width * (progress_percent / 100)
    if fill_width > 0:
        drawing.add(Rect(0, 0, fill_width, height, fillColor=fill_color, strokeColor=None))
    
    return drawing

def generate_pdf_report(problem_file):
    """Generate actual PDF report"""
    try:
        export_data = create_pdf_export_data(problem_file)
        if not export_data:
            return None
        
        # Create PDF buffer
        buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.darkblue
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.darkblue,
            borderWidth=1,
            borderColor=colors.lightgrey,
            backColor=colors.lightgrey,
            leftIndent=6,
            rightIndent=6,
            spaceBefore=6,
            spaceAfter=12
        )
        
        # Build PDF content
        story = []
        
        # Title and header
        story.append(Paragraph("📊 Project Analytics Report", title_style))
        story.append(Spacer(1, 12))
        
        # Project info table
        project_info = [
            ['Project Name:', export_data['project']['name']],
            ['Owner:', export_data['project']['owner']],
            ['Project Period:', f"{export_data['project']['start_date']} to {export_data['project']['end_date']}"],
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M')]
        ]
        
        project_table = Table(project_info, colWidths=[2*inch, 4*inch])
        project_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(project_table)
        story.append(Spacer(1, 20))
        
        # Project Summary
        story.append(Paragraph("📈 Project Summary", heading_style))
        
        summary_data = [
            ['Metric', 'Value'],
            ['Total Tasks', str(export_data['summary']['total_tasks'])],
            ['Total Subtasks', str(export_data['summary']['total_subtasks'])],
            ['Completed Subtasks', str(export_data['summary']['completed_subtasks'])],
            ['Completion Rate', export_data['summary']['completion_rate']],
            ['Total Comments', str(export_data['summary']['total_comments'])],
            ['Resolved Comments', str(export_data['summary']['resolved_comments'])]
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Team Workload
        story.append(Paragraph("👥 Team Workload", heading_style))
        
        workload_data = [['Team Member', 'Total Subtasks', 'Completed', 'Completion Rate', 'Progress']]
        
        for user, workload in export_data['team_workload'].items():
            completion_rate = (workload['completed'] / workload['total'] * 100) if workload['total'] > 0 else 0
            workload_data.append([
                user,
                str(workload['total']),
                str(workload['completed']),
                f"{completion_rate:.1f}%",
                ""  # Progress bar will be added as drawing
            ])
        
        workload_table = Table(workload_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
        
        # Add progress bars to the table
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        workload_table.setStyle(TableStyle(table_style))
        story.append(workload_table)
        story.append(Spacer(1, 20))
        
        # Comments Activity
        story.append(Paragraph("💬 Comments Activity", heading_style))
        
        comments_data = [['User', 'Total', 'Resolved', 'Resolution Rate', 'Mentions Given', 'Mentions Received', 'Admin', 'Partner', 'User']]
        
        for user, activity in export_data['comments_activity'].items():
            resolution_rate = (activity['resolved'] / activity['total'] * 100) if activity['total'] > 0 else 0
            comments_data.append([
                user,
                str(activity['total']),
                str(activity['resolved']),
                f"{resolution_rate:.1f}%",
                str(activity['mentions_given']),
                str(activity['mentions_received']),
                str(activity['as_admin']),
                str(activity['as_partner']),
                str(activity['as_user'])
            ])
        
        comments_table = Table(comments_data, colWidths=[1*inch, 0.6*inch, 0.6*inch, 0.8*inch, 0.7*inch, 0.7*inch, 0.5*inch, 0.6*inch, 0.5*inch])
        comments_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(comments_table)
        story.append(Spacer(1, 20))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=1,  # Center
            textColor=colors.grey
        )
        
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"Generated by Problem File Tracker • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
        
        # Build PDF
        doc.build(story)
        
        # Return PDF buffer
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        return None

def show_file_analytics(problem_file):
    """Display enhanced file analytics tab with actual PDF export"""
    st.subheader("📊 Project Analytics")
    
    # PDF Export button at the top
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("📄 Export PDF Report", use_container_width=True):
            with st.spinner("Generating PDF report..."):
                pdf_data = generate_pdf_report(problem_file)
                if pdf_data:
                    # Create filename with project name and date
                    project_name = problem_file.get('problem_name', 'project').replace(' ', '_')
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    filename = f"{project_name} - {current_date}.pdf"
                    
                    # Encode PDF for download
                    b64 = base64.b64encode(pdf_data).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">📄 Download PDF Report</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success(f"📊 PDF Report generated successfully! Click the link above to download '{filename}'")
                else:
                    st.error("Failed to generate PDF report. Please try again.")
    
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
    
    # Enhanced Comments activity analysis with resolution tracking
    st.subheader("💬 Enhanced Comments Activity")
    
    file_comments, resolved_comments = analyze_comments_for_file(problem_file)
    
    if file_comments:
        # Summary metrics
        total_comments = sum(data['total'] for data in file_comments.values())
        total_mentions = sum(data['mentions_given'] for data in file_comments.values())
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Comments", total_comments)
        with col2:
            st.metric("Resolved Comments", resolved_comments)
        with col3:
            st.metric("Resolution Rate", f"{(resolved_comments/total_comments*100):.1f}%" if total_comments > 0 else "0%")
        with col4:
            st.metric("Total @Mentions", total_mentions)
        
        # Detailed comments table
        comments_data = []
        for user, data in file_comments.items():
            resolution_rate = (data['resolved'] / data['total'] * 100) if data['total'] > 0 else 0
            comments_data.append({
                'User': user,
                'Total Comments': data['total'],
                'Resolved': data['resolved'],
                'Resolution Rate': f"{resolution_rate:.1f}%",
                'Mentions Given': data['mentions_given'],
                'Mentions Received': data['mentions_received'],
                'As Admin': data['as_admin'],
                'As Partner': data['as_partner'],
                'As User': data['as_user']
            })
        
        df_comments = pd.DataFrame(comments_data)
        st.dataframe(df_comments, use_container_width=True)
        
        # Comments resolution chart
        if resolved_comments > 0:
            col1, col2 = st.columns(2)
            
            with col1:
                # Resolution rate by user
                resolution_data = [(user, data['resolved']) for user, data in file_comments.items() if data['resolved'] > 0]
                if resolution_data:
                    users, resolved_counts = zip(*resolution_data)
                    fig_resolution = px.bar(
                        x=list(users),
                        y=list(resolved_counts),
                        title="Resolved Comments by User",
                        labels={'x': 'User', 'y': 'Resolved Comments'}
                    )
                    st.plotly_chart(fig_resolution, use_container_width=True)
            
            with col2:
                # Mentions network
                mention_data = [(user, data['mentions_given'], data['mentions_received']) 
                              for user, data in file_comments.items()]
                if mention_data:
                    users, given, received = zip(*mention_data)
                    fig_mentions = go.Figure()
                    fig_mentions.add_trace(go.Bar(name='Given', x=list(users), y=list(given)))
                    fig_mentions.add_trace(go.Bar(name='Received', x=list(users), y=list(received)))
                    fig_mentions.update_layout(title="@Mentions Given vs Received", barmode='group')
                    st