"""
Email handler module for SendGrid integration
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

def send_partner_comment_notification(file_owner, partner_name, file_name, task_name, comment_text):
    """Send email notification when partner comments"""
    print(f"Attempting to send email for file_owner: {file_owner}")

    owner_email = get_user_email(file_owner)
    print(f"Found email for {file_owner}: {owner_email}")

    if not owner_email:
        print(f"No email configured for user {file_owner}")
        return
    
    subject = f"New Comment on '{file_name}'"
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2f74c0;">New Partner Comment</h2>
                
                <p>Hi {file_owner},</p>
                
                <p><strong>{partner_name}</strong> has commented on your problem file:</p>
                
                <div style="background: #f5f5f5; padding: 15px; border-left: 4px solid #2f74c0; margin: 20px 0;">
                    <p><strong>Problem File:</strong> {file_name}</p>
                    <p><strong>Task/Subtask:</strong> {task_name}</p>
                    <p><strong>Comment:</strong></p>
                    <p style="font-style: italic;">"{comment_text}"</p>
                </div>
                
                <p>Log in to the Problem File Tracker to view and respond to this comment.</p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="font-size: 12px; color: #666;">
                    This is an automated notification from Problem File Tracker.
                </p>
            </div>
        </body>
    </html>
    """
    
    send_email_async(owner_email, subject, html_content)

def send_deadline_notification(file_owner, file_name, task_details):
    """Send email notification for approaching deadlines"""
    owner_email = get_user_email(file_owner)
    if not owner_email:
        logger.info(f"No email configured for user {file_owner}")
        return
    
    subject = f"Upcoming Deadlines in '{file_name}'"
    
    # Build task list HTML
    tasks_html = ""
    for task in task_details:
        days_until = task['days_until']
        status_color = "#ff0000" if days_until <= 1 else "#ff9900"
        
        tasks_html += f"""
        <div style="background: #fff; border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px;">
            <p><strong>{task['task_name']}</strong></p>
            <p>Assigned to: {task['assigned_to']}</p>
            <p>Due: {task['due_date']} (<span style="color: {status_color};">{days_until} days remaining</span>)</p>
            <p>Progress: {task['progress']}%</p>
        </div>
        """
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ff9900;">⚠️ Upcoming Deadlines</h2>
                
                <p>Hi {file_owner},</p>
                
                <p>The following tasks in <strong>'{file_name}'</strong> have deadlines approaching:</p>
                
                <div style="background: #fff9e6; padding: 15px; border: 1px solid #ffcc00; margin: 20px 0;">
                    {tasks_html}
                </div>
                
                <p>Please log in to the Problem File Tracker to review and update these tasks.</p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="font-size: 12px; color: #666;">
                    This is an automated deadline reminder from Problem File Tracker.
                </p>
            </div>
        </body>
    </html>
    """
    
    send_email_async(owner_email, subject, html_content)

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