"""
Comments system component with email notifications
"""
import streamlit as st
import uuid
from datetime import datetime
from database import save_comment, delete_comment
from email_handler import send_partner_comment_notification, get_user_email

# ============================================================================
# MAIN COMMENTS SECTION
# ============================================================================

def show_comments_section(entity_type: str, entity_id: str, entity_name: str, 
                         file_owner: str = None, file_name: str = None):
    """
    Display comments section for tasks and subtasks with email notifications
    
    Args:
        entity_type: Type of entity ('task' or 'subtask')
        entity_id: Unique ID of the entity
        entity_name: Display name of the entity
        file_owner: Username of the problem file owner
        file_name: Name of the problem file
    """
    st.markdown(f"### 💬 Comments for {entity_name}")
    
    # Debug panel for troubleshooting
    show_debug_panel(file_owner, file_name)
    
    # Check email notification conditions
    can_notify = check_notification_conditions(file_owner)
    
    # Get existing comments
    entity_comments = get_entity_comments(entity_type, entity_id)
    
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

def show_debug_panel(file_owner: str, file_name: str):
    """Show debug information panel (REMOVE IN PRODUCTION)"""
    with st.expander("🔍 Debug Information", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**File Info:**")
            st.code(f"Owner: {file_owner}")
            st.code(f"Name: {file_name}")
            st.code(f"Type: {type(file_owner)}")
        
        with col2:
            st.markdown("**Current User:**")
            st.code(f"User: {st.session_state.current_user}")
            st.code(f"Role: {st.session_state.user_role}")
            is_different = file_owner != st.session_state.current_user if file_owner else False
            st.code(f"Different: {is_different}")
        
        with col3:
            st.markdown("**Email Status:**")
            owner_email = get_user_email(file_owner) if file_owner else None
            st.code(f"Email: {owner_email or 'None'}")
            st.code(f"Can Send: {bool(owner_email and is_different)}")
            
            # Test email lookup
            if st.button("Test Email Lookup"):
                test_email_lookup(file_owner)

def test_email_lookup(file_owner: str):
    """Test email lookup functionality"""
    st.write("Testing email lookup...")
    
    # Test direct lookup
    if file_owner:
        email = get_user_email(file_owner)
        st.write(f"Lookup '{file_owner}': {email}")
    
    # Show all configured emails
    try:
        all_emails = st.secrets.get("user_emails", {})
        st.write("Configured users:")
        for user, email in all_emails.items():
            st.write(f"  • {user}: {email}")
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
        return False
    
    # Check if commenting on someone else's file
    is_other_file = file_owner != st.session_state.current_user
    
    # Check if owner has email configured
    owner_email = get_user_email(file_owner)
    
    return is_other_file and owner_email is not None

def get_entity_comments(entity_type: str, entity_id: str) -> dict:
    """
    Get all comments for a specific entity
    
    Returns:
        dict: Comments for the entity
    """
    entity_comments = {}
    all_comments = st.session_state.data.get('comments', {})
    
    for comment_id, comment in all_comments.items():
        if (comment.get('entity_type') == entity_type and 
            comment.get('entity_id') == entity_id):
            entity_comments[comment_id] = comment
    
    return entity_comments

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
        # Add to session state
        if 'comments' not in st.session_state.data:
            st.session_state.data['comments'] = {}
        st.session_state.data['comments'][comment_id] = comment_data
        
        # Send email notification if conditions are met
        email_sent = False
        if can_notify and file_owner and file_name:
            email_sent = send_email_notification(
                file_owner=file_owner,
                commenter=st.session_state.current_user,
                file_name=file_name,
                entity_name=entity_name,
                comment_text=comment_text,
                is_reply=is_reply
            )
        
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

def send_email_notification(file_owner: str, commenter: str, file_name: str,
                           entity_name: str, comment_text: str, is_reply: bool) -> bool:
    """
    Send email notification for comment
    
    Returns:
        bool: True if email was sent successfully
    """
    try:
        # Get owner's email
        owner_email = get_user_email(file_owner)
        if not owner_email:
            st.warning(f"No email found for {file_owner}")
            return False
        
        # Prepare task name for email
        if is_reply:
            task_name = f"Reply in {entity_name}"
        else:
            task_name = entity_name
        
        # Send notification
        send_partner_comment_notification(
            file_owner=file_owner,
            partner_name=commenter,
            file_name=file_name,
            task_name=task_name,
            comment_text=comment_text
        )
        
        return True
        
    except Exception as e:
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
        key=lambda x: x[1].get('created_at', datetime.now()),
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
        if comment_id in st.session_state.data.get('comments', {}):
            del st.session_state.data['comments'][comment_id]
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
        key=lambda x: x[1].get('created_at', datetime.now())
    )