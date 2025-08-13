"""
Comments system component with email notifications - Fixed Version
"""
import streamlit as st
import uuid
from datetime import datetime
from database import save_comment, delete_comment, init_supabase
from email_handler import send_partner_comment_notification, get_user_email

# ============================================================================
# DATABASE HELPER FUNCTIONS
# ============================================================================

def get_supabase_client():
    """Get Supabase client"""
    from database import init_supabase
    return init_supabase()

def get_file_owner_from_entity(entity_type: str, entity_id: str):
    """
    Get file owner and name by looking up through database relationships
    
    Args:
        entity_type: 'task' or 'subtask'
        entity_id: UUID of the entity
        
    Returns:
        tuple: (file_owner, file_name) or (None, None)
    """
    try:
        supabase = get_supabase_client()
        
        if entity_type == 'task':
            # Get task and its problem file
            response = supabase.table('tasks').select(
                'problem_files(owner, problem_name)'
            ).eq('id', entity_id).execute()
            
            if response.data and len(response.data) > 0:
                problem_file = response.data[0].get('problem_files')
                if problem_file:
                    return problem_file['owner'], problem_file['problem_name']
        
        elif entity_type == 'subtask':
            # Get subtask -> task -> problem file
            response = supabase.table('subtasks').select(
                'tasks(problem_files(owner, problem_name))'
            ).eq('id', entity_id).execute()
            
            if response.data and len(response.data) > 0:
                task = response.data[0].get('tasks')
                if task:
                    problem_file = task.get('problem_files')
                    if problem_file:
                        return problem_file['owner'], problem_file['problem_name']
        
        print(f"[DB] Could not find file owner for {entity_type} {entity_id}")
        return None, None
        
    except Exception as e:
        print(f"[DB ERROR] Error getting file owner: {e}")
        return None, None

def get_entity_comments_from_db(entity_type: str, entity_id: str):
    """
    Get all comments for a specific entity from database
    
    Returns:
        dict: Comments for the entity {comment_id: comment_data}
    """
    try:
        supabase = get_supabase_client()
        
        response = supabase.table('comments').select('*').eq(
            'entity_type', entity_type
        ).eq('entity_id', entity_id).order('created_at', desc=False).execute()
        
        # Convert to dict format for existing display code
        entity_comments = {}
        if response.data:
            for comment in response.data:
                entity_comments[comment['id']] = comment
                
        print(f"[DB] Found {len(entity_comments)} comments for {entity_type} {entity_id}")
        return entity_comments
        
    except Exception as e:
        print(f"[DB ERROR] Error getting comments: {e}")
        return {}

# ============================================================================
# MAIN COMMENTS SECTION
# ============================================================================

def show_comments_section(entity_type: str, entity_id: str, entity_name: str):
    """
    Display comments section for tasks and subtasks with email notifications
    
    Args:
        entity_type: Type of entity ('task' or 'subtask')
        entity_id: Unique ID of the entity
        entity_name: Display name of the entity
    """
    st.markdown(f"### 💬 Comments for {entity_name}")
    
    # Get file owner and name from database
    file_owner, file_name = get_file_owner_from_entity(entity_type, entity_id)
    
    if not file_owner:
        st.error("❌ Could not determine file owner for notifications")
        return
    
    # Debug panel for troubleshooting
    if st.secrets.get("debug_mode", False):
        show_debug_panel(entity_type, entity_id, file_owner, file_name, entity_name)
    
    # Check email notification conditions
    can_notify = check_notification_conditions(file_owner)
    
    # Get existing comments from database
    entity_comments = get_entity_comments_from_db(entity_type, entity_id)
    
    # Show comment form
    show_comment_form(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        file_owner=file_owner,
        file_name=file_name,
        can_notify=can_notify
    )
    
    # Display existing comments
    if entity_comments:
        st.markdown("---")
        st.markdown("#### Existing Comments")
        display_comments_list(
            entity_comments=entity_comments,
            entity_type=entity_type,
            entity_id=entity_id,
            file_owner=file_owner,
            file_name=file_name,
            entity_name=entity_name
        )
    else:
        st.info("💭 No comments yet. Be the first to comment!")

# ============================================================================
# DEBUG FUNCTIONS
# ============================================================================

def show_debug_panel(entity_type: str, entity_id: str, file_owner: str, file_name: str, entity_name: str):
    """Show debug information panel"""
    with st.expander("🔍 Debug Information", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Entity Info:**")
            st.code(f"Type: {entity_type}")
            st.code(f"ID: {entity_id}")
            st.code(f"Name: {entity_name}")
        
        with col2:
            st.markdown("**File Context:**")
            st.code(f"Owner: {file_owner}")
            st.code(f"File: {file_name}")
            st.code(f"Owner Type: {type(file_owner)}")
        
        with col3:
            st.markdown("**Current User:**")
            st.code(f"User: {st.session_state.current_user}")
            st.code(f"Role: {st.session_state.user_role}")
            
            is_different = file_owner != st.session_state.current_user if file_owner else False
            st.code(f"Different User: {is_different}")
            
            owner_email = get_user_email(file_owner) if file_owner else None
            st.code(f"Owner Email: {owner_email or 'None'}")
            
            can_send = bool(owner_email and is_different)
            st.code(f"Can Send Email: {can_send}")
            
            # Test email lookup
            if st.button("🧪 Test Email Lookup"):
                test_email_lookup(file_owner)

def test_email_lookup(file_owner: str):
    """Test email lookup functionality"""
    st.write("**Email Lookup Test Results:**")
    
    if not file_owner:
        st.error("No file owner to test")
        return
    
    # Show raw file_owner value
    st.code(f"Testing owner: '{file_owner}'")
    st.code(f"Length: {len(file_owner)}")
    st.code(f"Repr: {repr(file_owner)}")
    
    # Test direct lookup
    email = get_user_email(file_owner)
    st.code(f"Email result: {email}")
    
    # Show all configured emails
    try:
        all_emails = st.secrets.get("user_emails", {})
        st.write("**Configured users in secrets:**")
        for user, email in all_emails.items():
            match_status = "✅ MATCH" if user == file_owner else ""
            st.code(f"{repr(user)}: {email} {match_status}")
    except Exception as e:
        st.error(f"Error accessing user_emails: {e}")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def check_notification_conditions(file_owner: str) -> bool:
    """
    Check if email notifications should be sent
    
    Returns:
        bool: True if notifications should be sent
    """
    if not file_owner:
        print(f"[NOTIFICATION] No file owner provided")
        return False
    
    # Check if commenting on someone else's file
    is_other_file = file_owner != st.session_state.current_user
    if not is_other_file:
        print(f"[NOTIFICATION] User commenting on own file, no notification needed")
        return False
    
    # Check if owner has email configured
    owner_email = get_user_email(file_owner)
    has_email = owner_email is not None
    
    print(f"[NOTIFICATION] Owner: {file_owner}, Email: {owner_email}, Can notify: {is_other_file and has_email}")
    return is_other_file and has_email

# ============================================================================
# COMMENT FORM
# ============================================================================

def show_comment_form(entity_type: str, entity_id: str, entity_name: str,
                     file_owner: str, file_name: str, can_notify: bool):
    """Display the add comment form"""
    
    with st.expander("➕ Add New Comment", expanded=False):
        # Show notification status
        if can_notify:
            owner_email = get_user_email(file_owner)
            st.success(f"📧 Your comment will notify **{file_owner}** at {owner_email}")
        elif file_owner and file_owner != st.session_state.current_user:
            st.warning(f"⚠️ {file_owner} has no email configured - no notification will be sent")
        elif file_owner == st.session_state.current_user:
            st.info("ℹ️ You're commenting on your own file - no email notification needed")
        
        # Comment form
        with st.form(f"comment_form_{entity_type}_{entity_id}", clear_on_submit=True):
            comment_text = st.text_area(
                "Write your comment:",
                placeholder="Share your thoughts...",
                key=f"comment_input_{entity_type}_{entity_id}"
            )
            
            submitted = st.form_submit_button("💬 Post Comment", use_container_width=True)
            
            if submitted:
                if comment_text and comment_text.strip():
                    handle_comment_submission(
                        comment_text=comment_text.strip(),
                        entity_type=entity_type,
                        entity_id=entity_id,
                        entity_name=entity_name,
                        file_owner=file_owner,
                        file_name=file_name,
                        can_notify=can_notify,
                        is_reply=False,
                        parent_id=None
                    )
                else:
                    st.error("⚠️ Please enter a comment before posting.")

def handle_comment_submission(comment_text: str, entity_type: str, entity_id: str,
                             entity_name: str, file_owner: str, file_name: str,
                             can_notify: bool, is_reply: bool, parent_id: str = None):
    """Handle comment submission with email notification"""
    
    print(f"[COMMENT_SUBMIT] Handling comment submission")
    print(f"[COMMENT_SUBMIT] Entity: {entity_type}/{entity_id}")
    print(f"[COMMENT_SUBMIT] File Owner: {file_owner}")
    print(f"[COMMENT_SUBMIT] Can Notify: {can_notify}")
    
    # Create comment data
    comment_id = str(uuid.uuid4())
    comment_data = {
        'entity_type': entity_type,
        'entity_id': entity_id,
        'user_name': st.session_state.current_user,
        'text': comment_text,
        'created_at': datetime.now(),
        'parent_id': parent_id,
        'user_role': st.session_state.user_role
    }
    
    # Save comment to database
    if save_comment(comment_id, comment_data):
        print(f"[COMMENT_SUBMIT] Comment saved successfully: {comment_id}")
        
        # Send email notification if conditions are met
        email_sent = False
        if can_notify and file_owner and file_name:
            print(f"[COMMENT_SUBMIT] Attempting to send email notification")
            email_sent = send_email_notification(
                file_owner=file_owner,
                commenter=st.session_state.current_user,
                file_name=file_name,
                entity_name=entity_name,
                comment_text=comment_text,
                is_reply=is_reply
            )
        else:
            print(f"[COMMENT_SUBMIT] Email notification skipped - conditions not met")
        
        # Show success message
        if email_sent:
            st.success(f"✅ {'Reply' if is_reply else 'Comment'} posted and {file_owner} notified via email!")
        else:
            st.success(f"✅ {'Reply' if is_reply else 'Comment'} posted successfully!")
        
        # Clear reply state if this was a reply
        if is_reply and parent_id:
            if f"replying_to_{parent_id}" in st.session_state:
                del st.session_state[f"replying_to_{parent_id}"]
        
        st.rerun()
    else:
        st.error("❌ Failed to save comment. Please try again.")
        print(f"[COMMENT_SUBMIT] Failed to save comment")

def send_email_notification(file_owner: str, commenter: str, file_name: str,
                           entity_name: str, comment_text: str, is_reply: bool) -> bool:
    """
    Send email notification for comment
    
    Returns:
        bool: True if email was sent successfully
    """
    try:
        print(f"[EMAIL_NOTIFY] Preparing notification for {file_owner}")
        
        # Get owner's email
        owner_email = get_user_email(file_owner)
        if not owner_email:
            print(f"[EMAIL_NOTIFY] No email found for {file_owner}")
            st.warning(f"No email configured for {file_owner}")
            return False
        
        print(f"[EMAIL_NOTIFY] Found email for {file_owner}: {owner_email}")
        
        # Prepare task name for email
        if is_reply:
            task_name = f"Reply in {entity_name}"
        else:
            task_name = entity_name
        
        # Send notification
        print(f"[EMAIL_NOTIFY] Calling send_partner_comment_notification")
        send_partner_comment_notification(
            file_owner=file_owner,
            partner_name=commenter,
            file_name=file_name,
            task_name=task_name,
            comment_text=comment_text
        )
        
        print(f"[EMAIL_NOTIFY] Email notification sent successfully")
        return True
        
    except Exception as e:
        print(f"[EMAIL_NOTIFY ERROR] {str(e)}")
        st.error(f"Email error: {str(e)}")
        return False

# ============================================================================
# COMMENT DISPLAY
# ============================================================================

def display_comments_list(entity_comments: dict, entity_type: str, entity_id: str,
                         file_owner: str, file_name: str, entity_name: str):
    """Display list of comments with threading"""
    
    # Get root comments (no parent)
    root_comments = {
        cid: comment for cid, comment in entity_comments.items()
        if not comment.get('parent_id')
    }
    
    # Sort by newest first
    sorted_comments = sorted(
        root_comments.items(),
        key=lambda x: parse_timestamp(x[1].get('created_at')),
        reverse=True
    )
    
    # Display each comment thread
    for comment_id, comment in sorted_comments:
        display_comment_with_replies(
            comment_id=comment_id,
            comment=comment,
            all_comments=entity_comments,
            entity_type=entity_type,
            entity_id=entity_id,
            file_owner=file_owner,
            file_name=file_name,
            entity_name=entity_name,
            depth=0
        )

def display_comment_with_replies(comment_id: str, comment: dict, all_comments: dict,
                                entity_type: str, entity_id: str, file_owner: str,
                                file_name: str, entity_name: str, depth: int):
    """Display a single comment with its replies"""
    
    # Create indentation for nested comments
    if depth > 0:
        cols = st.columns([depth * 0.05, 1])
        container = cols[1]
    else:
        container = st.container()
    
    with container:
        # Comment container
        with st.container(border=True):
            # Header row
            col1, col2, col3 = st.columns([0.1, 5, 0.5])
            
            # Role badge
            with col1:
                role_badge = get_role_badge(comment.get('user_role', 'User'))
                st.write(role_badge)
            
            # Comment content
            with col2:
                # User info and timestamp
                user_name = comment.get('user_name') or comment.get('user', 'Unknown')
                timestamp = format_timestamp(comment.get('created_at'))
                st.markdown(f"**{user_name}** · {timestamp}")
                
                # Comment text
                st.write(comment['text'])
                
                # Reply button
                if st.button("↩️ Reply", key=f"reply_{comment_id}", use_container_width=False):
                    st.session_state[f"replying_to_{comment_id}"] = True
            
            # Delete button
            with col3:
                if can_delete_comment(comment):
                    if st.button("🗑️", key=f"delete_{comment_id}", help="Delete comment"):
                        delete_comment_handler(comment_id)
            
            # Reply form (if replying)
            if st.session_state.get(f"replying_to_{comment_id}", False):
                show_reply_form(
                    parent_id=comment_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    file_owner=file_owner,
                    file_name=file_name
                )
        
        # Display replies
        replies = get_replies(comment_id, all_comments)
        for reply_id, reply in replies:
            display_comment_with_replies(
                comment_id=reply_id,
                comment=reply,
                all_comments=all_comments,
                entity_type=entity_type,
                entity_id=entity_id,
                file_owner=file_owner,
                file_name=file_name,
                entity_name=entity_name,
                depth=depth + 1
            )

def show_reply_form(parent_id: str, entity_type: str, entity_id: str,
                   entity_name: str, file_owner: str, file_name: str):
    """Show reply form for a comment"""
    
    can_notify = check_notification_conditions(file_owner)
    
    with st.form(f"reply_form_{parent_id}", clear_on_submit=True):
        if can_notify:
            st.info(f"📧 Your reply will notify {file_owner}")
        
        reply_text = st.text_area("Write your reply:", key=f"reply_input_{parent_id}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.form_submit_button("Post Reply", use_container_width=True):
                if reply_text and reply_text.strip():
                    handle_comment_submission(
                        comment_text=reply_text.strip(),
                        entity_type=entity_type,
                        entity_id=entity_id,
                        entity_name=entity_name,
                        file_owner=file_owner,
                        file_name=file_name,
                        can_notify=can_notify,
                        is_reply=True,
                        parent_id=parent_id
                    )
                else:
                    st.error("Please enter a reply.")
        
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                del st.session_state[f"replying_to_{parent_id}"]
                st.rerun()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_role_badge(role: str) -> str:
    """Get emoji badge for user role"""
    badges = {
        'Admin': '👑',
        'Partner': '🤝',
        'User': '👤'
    }
    return badges.get(role, '👤')

def parse_timestamp(timestamp):
    """Parse timestamp for sorting - handles both string and datetime objects"""
    if not timestamp:
        return datetime.min
    
    if isinstance(timestamp, str):
        try:
            # Handle ISO format with timezone
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            try:
                # Try parsing without timezone
                return datetime.fromisoformat(timestamp)
            except:
                return datetime.min
    
    if isinstance(timestamp, datetime):
        return timestamp
    
    return datetime.min

def format_timestamp(timestamp) -> str:
    """Format timestamp for display"""
    if not timestamp:
        return "Unknown time"
    
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            return "Unknown time"
    
    if isinstance(timestamp, datetime):
        return timestamp.strftime('%Y-%m-%d %H:%M')
    
    return "Unknown time"

def can_delete_comment(comment: dict) -> bool:
    """Check if current user can delete a comment"""
    user_name = comment.get('user_name') or comment.get('user', '')
    return (
        user_name == st.session_state.current_user or
        st.session_state.user_role in ['Admin', 'Partner']
    )

def delete_comment_handler(comment_id: str):
    """Handle comment deletion"""
    if delete_comment(comment_id):
        st.success("Comment deleted!")
        st.rerun()
    else:
        st.error("Failed to delete comment.")

def get_replies(parent_id: str, all_comments: dict) -> list:
    """Get all replies to a comment, sorted by date"""
    replies = [
        (cid, comment) for cid, comment in all_comments.items()
        if comment.get('parent_id') == parent_id
    ]
    
    return sorted(
        replies,
        key=lambda x: parse_timestamp(x[1].get('created_at'))
    )