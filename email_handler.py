"""
Email handler module for SendGrid integration with enhanced templates
"""
import streamlit as st
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import threading
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App URL constant
APP_URL = "https://no-more-problemspy.streamlit.app/"

def get_sendgrid_client():
    """Initialize SendGrid client"""
    try:
        api_key = st.secrets.get("sendgrid", {}).get("api_key")
        if api_key:
            return SendGridAPIClient(api_key)
        return None
    except Exception as e:
        logger.error(f"Failed to initialize SendGrid: {e}")
        return None

def get_user_email(username):
    """Get user email from secrets - handles case sensitivity and whitespace"""
    try:
        if not username:
            print(f"[EMAIL] No username provided")
            return None
            
        user_emails = st.secrets.get("user_emails", {})
        
        # Clean the username (remove whitespace)
        username_clean = username.strip()
        
        print(f"[EMAIL] Looking for email for: '{username}' (cleaned: '{username_clean}')")
        print(f"[EMAIL] Available users: {list(user_emails.keys())}")
        
        # Try exact match first
        if username_clean in user_emails:
            email = user_emails[username_clean]
            print(f"[EMAIL] Found exact match: {email}")
            return email
        
        # Try case-insensitive match
        for key, value in user_emails.items():
            if key.lower() == username_clean.lower():
                print(f"[EMAIL] Found case-insensitive match: {key} -> {value}")
                return value
        
        # Try partial match (in case there's extra text)
        for key, value in user_emails.items():
            if key.lower() in username_clean.lower() or username_clean.lower() in key.lower():
                print(f"[EMAIL] Found partial match: {key} -> {value}")
                return value
        
        print(f"[EMAIL] No email found for: '{username}'")
        print(f"[EMAIL] Available keys: {list(user_emails.keys())}")
        return None
        
    except Exception as e:
        print(f"[EMAIL ERROR] Exception in get_user_email: {e}")
        return None

def create_email_template(title, main_content, cta_text="Open Problem File Tracker", include_footer=True):
    """Create standardized email template with app link"""
    
    footer_html = ""
    if include_footer:
        footer_html = f"""
        <div style="text-align: center; margin: 30px 0;">
            <a href="{APP_URL}" 
               style="background-color: #2f74c0; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                {cta_text}
            </a>
        </div>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
        <p style="font-size: 12px; color: #666; text-align: center;">
            This is an automated notification from <a href="{APP_URL}" style="color: #2f74c0;">Problem File Tracker</a>.<br>
            Need help? Visit our app for more information.
        </p>
        """
    
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                
                <!-- Header -->
                <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #2f74c0;">
                    <h1 style="color: #2f74c0; margin: 0;">📁 Problem File Tracker</h1>
                </div>
                
                <!-- Title -->
                <h2 style="color: #2f74c0; margin: 20px 0;">{title}</h2>
                
                <!-- Main Content -->
                {main_content}
                
                <!-- Footer with CTA -->
                {footer_html}
            </div>
        </body>
    </html>
    """

def send_email_async(to_email, subject, html_content):
    """Send email asynchronously to avoid blocking UI"""
    def send():
        try:
            print(f"[SENDGRID] Starting email send to: {to_email}")
            
            sg = get_sendgrid_client()
            if not sg:
                print("[SENDGRID ERROR] SendGrid client not available - check API key")
                return
            
            from_email = st.secrets.get("sendgrid", {}).get("from_email", "noreply@problemtracker.com")
            print(f"[SENDGRID] From: {from_email}, To: {to_email}")
            
            message = Mail(
                from_email=from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            print(f"[SENDGRID] Sending email with subject: {subject}")
            response = sg.send(message)
            print(f"[SENDGRID SUCCESS] Email sent! Status code: {response.status_code}")
            print(f"[SENDGRID SUCCESS] Response headers: {response.headers}")
            
        except Exception as e:
            print(f"[SENDGRID ERROR] Failed to send email: {str(e)}")
            print(f"[SENDGRID ERROR] Exception type: {type(e).__name__}")
            import traceback
            print(f"[SENDGRID ERROR] Traceback: {traceback.format_exc()}")
    
    # Run in separate thread
    print(f"[SENDGRID] Starting thread for email to {to_email}")
    thread = threading.Thread(target=send)
    thread.daemon = True
    thread.start()

def send_new_problem_file_notification(owner, file_name, created_by, start_date, end_date):
    """Send email notification when a new problem file is created"""
    print(f"Attempting to send new problem file email to: {owner}")

    owner_email = get_user_email(owner)
    print(f"Found email for {owner}: {owner_email}")

    if not owner_email:
        print(f"No email configured for user {owner}")
        return
    
    subject = f"New Problem File Assigned: '{file_name}'"
    
    main_content = f"""
    <p>Hi <strong>{owner}</strong>,</p>
    
    <p>A new problem file has been created and assigned to you:</p>
    
    <div style="background: #e8f4fd; padding: 20px; border-left: 4px solid #2f74c0; margin: 20px 0; border-radius: 5px;">
        <h3 style="margin-top: 0; color: #2f74c0;">📁 {file_name}</h3>
        <p><strong>Created by:</strong> {created_by}</p>
        <p><strong>Project Start:</strong> {start_date}</p>
        <p><strong>Project End:</strong> {end_date}</p>
        <p><strong>Status:</strong> Ready for setup</p>
    </div>
    
    <p><strong>Next Steps:</strong></p>
    <ul>
        <li>Review the project timeline and objectives</li>
        <li>Add tasks and subtasks to organize the work</li>
        <li>Assign team members to specific subtasks</li>
        <li>Set up key milestones and deadlines</li>
        <li>Add relevant contacts and SharePoint links</li>
    </ul>
    
    <p>Get started by accessing your new problem file in the tracker.</p>
    """
    
    html_content = create_email_template(
        title="🎉 New Problem File Created",
        main_content=main_content,
        cta_text="Open Your Problem File"
    )
    
    send_email_async(owner_email, subject, html_content)

def send_partner_comment_notification(file_owner, partner_name, file_name, task_name, comment_text):
    """Send email notification when partner comments"""
    print(f"Attempting to send partner comment email for file_owner: {file_owner}")

    owner_email = get_user_email(file_owner)
    print(f"Found email for {file_owner}: {owner_email}")

    if not owner_email:
        print(f"No email configured for user {file_owner}")
        return
    
    subject = f"New Partner Comment on '{file_name}'"
    
    main_content = f"""
    <p>Hi <strong>{file_owner}</strong>,</p>
    
    <p><strong>{partner_name}</strong> has added a comment to your problem file:</p>
    
    <div style="background: #f8f9fa; padding: 20px; border-left: 4px solid #28a745; margin: 20px 0; border-radius: 5px;">
        <p><strong>📁 Problem File:</strong> {file_name}</p>
        <p><strong>📋 Task/Subtask:</strong> {task_name}</p>
        <div style="background: white; padding: 15px; border-radius: 5px; margin: 10px 0;">
            <p><strong>💬 Comment:</strong></p>
            <p style="font-style: italic; color: #555; border-left: 3px solid #ddd; padding-left: 15px;">"{comment_text}"</p>
        </div>
        <p><strong>👤 From:</strong> {partner_name} (Partner)</p>
    </div>
    
    <p>This comment may require your attention or response. Please review it at your earliest convenience.</p>
    """
    
    html_content = create_email_template(
        title="💬 New Partner Comment",
        main_content=main_content,
        cta_text="View Comment & Respond"
    )
    
    send_email_async(owner_email, subject, html_content)

def send_deadline_notification(file_owner, file_name, task_details):
    """Send email notification for approaching deadlines"""
    owner_email = get_user_email(file_owner)
    if not owner_email:
        logger.info(f"No email configured for user {file_owner}")
        return
    
    subject = f"⚠️ Upcoming Deadlines in '{file_name}'"
    
    # Build task list HTML
    tasks_html = ""
    urgent_count = 0
    
    for task in task_details:
        days_until = task['days_until']
        
        if days_until <= 1:
            status_color = "#dc3545"
            status_icon = "🔴"
            urgent_count += 1
        elif days_until <= 2:
            status_color = "#fd7e14"
            status_icon = "🟠"
        else:
            status_color = "#ffc107"
            status_icon = "🟡"
        
        progress_color = "#28a745" if task['progress'] >= 75 else "#ffc107" if task['progress'] >= 50 else "#dc3545"
        
        tasks_html += f"""
        <div style="background: white; border: 1px solid #dee2e6; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid {status_color};">
            <h4 style="margin: 0 0 10px 0; color: #333;">{status_icon} {task['task_name']}</h4>
            <div style="display: flex; justify-content: space-between; margin: 5px 0;">
                <span><strong>Assigned to:</strong> {task['assigned_to']}</span>
                <span style="color: {status_color}; font-weight: bold;">{days_until} days remaining</span>
            </div>
            <div style="margin: 5px 0;">
                <strong>Due Date:</strong> {task['due_date']}
            </div>
            <div style="margin: 10px 0;">
                <div style="background: #e9ecef; height: 8px; border-radius: 4px; overflow: hidden;">
                    <div style="background: {progress_color}; height: 100%; width: {task['progress']}%; transition: width 0.3s;"></div>
                </div>
                <small style="color: #666;">Progress: {task['progress']}%</small>
            </div>
        </div>
        """
    
    urgency_message = ""
    if urgent_count > 0:
        urgency_message = f"""
        <div style="background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <strong>⚠️ URGENT:</strong> {urgent_count} task(s) due within 24 hours!
        </div>
        """
    
    main_content = f"""
    <p>Hi <strong>{file_owner}</strong>,</p>
    
    <p>The following tasks in <strong>'{file_name}'</strong> have deadlines approaching:</p>
    
    {urgency_message}
    
    <div style="background: #fff3cd; padding: 20px; border: 1px solid #ffeaa7; margin: 20px 0; border-radius: 8px;">
        <h3 style="margin-top: 0; color: #856404;">📅 Upcoming Deadlines</h3>
        {tasks_html}
    </div>
    
    <p><strong>Recommended Actions:</strong></p>
    <ul>
        <li>Review task progress and update completion percentages</li>
        <li>Contact assigned team members if needed</li>
        <li>Adjust deadlines if necessary</li>
        <li>Add comments or notes for team coordination</li>
    </ul>
    
    <p>Stay on top of your project timeline by reviewing these tasks today.</p>
    """
    
    html_content = create_email_template(
        title="⏰ Deadline Alert",
        main_content=main_content,
        cta_text="Review Tasks & Update Progress"
    )
    
    send_email_async(owner_email, subject, html_content)

def send_task_assignment_notification(assigned_user, assigner, file_name, task_name, due_date):
    """Send email notification when a user is assigned to a new task"""
    user_email = get_user_email(assigned_user)
    if not user_email:
        print(f"No email configured for user {assigned_user}")
        return
    
    subject = f"New Task Assignment: '{task_name}'"
    
    main_content = f"""
    <p>Hi <strong>{assigned_user}</strong>,</p>
    
    <p>You have been assigned to a new task by <strong>{assigner}</strong>:</p>
    
    <div style="background: #e8f4fd; padding: 20px; border-left: 4px solid #2f74c0; margin: 20px 0; border-radius: 5px;">
        <h3 style="margin-top: 0; color: #2f74c0;">📋 {task_name}</h3>
        <p><strong>📁 Problem File:</strong> {file_name}</p>
        <p><strong>👤 Assigned by:</strong> {assigner}</p>
        <p><strong>📅 Due Date:</strong> {due_date}</p>
        <p><strong>🎯 Status:</strong> Ready to start</p>
    </div>
    
    <p><strong>Next Steps:</strong></p>
    <ul>
        <li>Review the task details and requirements</li>
        <li>Update progress as you work on the task</li>
        <li>Add comments if you have questions</li>
        <li>Mark as complete when finished</li>
    </ul>
    
    <p>Access the task details and start tracking your progress.</p>
    """
    
    html_content = create_email_template(
        title="📋 New Task Assignment",
        main_content=main_content,
        cta_text="View Task Details"
    )
    
    send_email_async(user_email, subject, html_content)

def check_and_send_deadline_alerts():
    """Check all problem files for approaching deadlines and send notifications"""
    try:
        if 'data' not in st.session_state or 'problem_files' not in st.session_state.data:
            return
        
        today = datetime.now().date()
        alert_threshold = timedelta(days=3)  # Alert when 3 days or less remaining
        
        for file_id, file_data in st.session_state.data['problem_files'].items():
            approaching_deadlines = []
            
            for task_id, task in file_data.get('tasks', {}).items():
                for subtask_id, subtask in task.get('subtasks', {}).items():
                    if subtask['progress'] < 100:  # Only check incomplete tasks
                        due_date = subtask['projected_end_date'].date()
                        days_until = (due_date - today).days
                        
                        if 0 <= days_until <= alert_threshold.days:
                            approaching_deadlines.append({
                                'task_name': f"{task['name']} - {subtask['name']}",
                                'assigned_to': subtask['assigned_to'],
                                'due_date': due_date.strftime('%Y-%m-%d'),
                                'days_until': days_until,
                                'progress': subtask['progress']
                            })
            
            # Send notification if there are approaching deadlines
            if approaching_deadlines:
                send_deadline_notification(
                    file_data['owner'],
                    file_data['problem_name'],
                    approaching_deadlines
                )
                
    except Exception as e:
        logger.error(f"Error checking deadlines: {e}")

def is_email_configured():
    """Check if email is properly configured"""
    try:
        api_key = st.secrets.get("sendgrid", {}).get("api_key")
        from_email = st.secrets.get("sendgrid", {}).get("from_email")
        return bool(api_key and from_email)
    except:
        return False