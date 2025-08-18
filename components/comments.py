"""
Enhanced Comments system with @mentions functionality
"""
import streamlit as st
import uuid
import re
from datetime import datetime
from database import save_comment, delete_comment, init_supabase
from email_handler import send_partner_comment_notification, get_user_email

# ============================================================================
# MENTIONS PROCESSING FUNCTIONS
# ============================================================================

def extract_mentions(text: str) -> list:
    """
    Extract @mentions from comment text
    
    Returns:
        list: List of mentioned usernames (without @)
    """
    # Find all @mentions (word characters only, no spaces)
    mentions = re.findall(r'@(\w+)', text)
    return list(set(mentions))  # Remove duplicates

def get_available_users() -> list:
    """Get list of users available for mentioning"""
    try:
        # First try to get from session state
        users = st.session_state.data.get('users', [])
        if users:
            print(f"[MENTIONS] Found users in session state: {users}")
            return users
        
        # Fallback: try to get from secrets or hardcoded list
        fallback_users = ['Admin', 'Partner', 'Haris', 'Stan']
        print(f"[MENTIONS] Using fallback users: {fallback_users}")
        return fallback_users
        
    except Exception as e:
        print(f"[MENTIONS ERROR] Error getting users: {e}")
        # Last resort fallback
        return ['Admin', 'Partner', 'User']

def validate_mentions(mentions: list) -> list:
    """
    Validate that mentioned users exist in the system
    
    Returns:
        list: Valid usernames that exist in the system
    """
    available_users = get_available_users()
    valid_mentions = []
    
    for mention in mentions:
        # Case-insensitive search for users
        for user in available_users:
            if user.lower() == mention.lower():
                valid_mentions.append(user)  # Use correct casing
                break
    
    return valid_mentions

def format_comment_with_mentions(text: str) -> str:
    """
    Format comment text to highlight @mentions
    
    Returns:
        str: HTML formatted text with highlighted mentions
    """
    available_users = get_available_users()
    
    def replace_mention(match):
        username = match.group(1)
        # Check if this is a valid user (case-insensitive)
        for user in available_users:
            if user.lower() == username.lower():
                return f'<span style="background-color: #e3f2fd; color: #1976d2; padding: 2px 4px; border-radius: 3px; font-weight: bold;">@{user}</span>'
        # If not a valid user, return as-is
        return match.group(0)
    
    # Replace @mentions with formatted spans
    formatted_text = re.sub(r'@(\w+)', replace_mention, text)
    return formatted_text

def send_mention_notifications(mentions: list, commenter: str, file_name: str, 
                             entity_name: str, comment_text: str, is_reply: bool = False):
    """
    Send email notifications to mentioned users
    
    Args:
        mentions: List of mentioned usernames
        commenter: Person who made the comment
        file_name: Name of the problem file
        entity_name: Name of the task/subtask
        comment_text: The comment text
        is_reply: Whether this is a reply or new comment
    """
    for mentioned_user in mentions:
        # Don't notify if user mentions themselves
        if mentioned_user == commenter:
            continue
            
        try:
            user_email = get_user_email(mentioned_user)
            if not user_email:
                print(f"[MENTION] No email found for mentioned user: {mentioned_user}")
                continue
            
            # Send mention notification
            send_mention_email_notification(
                mentioned_user=mentioned_user,
                commenter=commenter,
                file_name=file_name,
                entity_name=entity_name,
                comment_text=comment_text,
                is_reply=is_reply
            )
            print(f"[MENTION] Sent mention notification to {mentioned_user}")
            
        except Exception as e:
            print(f"[MENTION ERROR] Failed to notify {mentioned_user}: {e}")

def send_mention_email_notification(mentioned_user: str, commenter: str, file_name: str,
                                  entity_name: str, comment_text: str, is_reply: bool):
    """Send email notification for @mention"""
    from email_handler import send_email_async
    
    subject = f"You were mentioned in '{file_name}'"
    
    # Create a clean version of the comment for email (remove HTML formatting)
    clean_comment = re.sub(r'<[^>]+>', '', comment_text)
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ff6b35;">👋 You were mentioned!</h2>
                
                <p>Hi {mentioned_user},</p>
                
                <p><strong>{commenter}</strong> mentioned you in a comment:</p>
                
                <div style="background: #fff3e0; padding: 15px; border-left: 4px solid #ff6b35; margin: 20px 0;">
                    <p><strong>Problem File:</strong> {file_name}</p>
                    <p><strong>Task/Subtask:</strong> {entity_name}</p>
                    <p><strong>{'Reply' if is_reply else 'Comment'}:</strong></p>
                    <p style="font-style: italic; background: white; padding: 10px; border-radius: 4px;">"{clean_comment}"</p>
                </div>
                
                <p>Log in to the Problem File Tracker to view the full conversation and respond.</p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="font-size: 12px; color: #666;">
                    This is an automated mention notification from Problem File Tracker.
                </p>
            </div>
        </body>
    </html>
    """
    
    send_email_async(mentioned_user + "@example.com", subject, html_content)

# ============================================================================
# DATABASE HELPER FUNCTIONS
# ============================================================================

def get_supabase_client():
    """Get Supabase client"""
    from database import init_supabase
    return init_supabase()

def get_file_owner_from_entity(entity_type: str, entity_id: str):
    """Get file owner and name by looking up through database relationships"""
    try:
        supabase = get_supabase_client()
        
        if entity_type == 'task':
            response = supabase.table('tasks').select(
                'problem_files(owner, problem_name)'
            ).eq('id', entity_id).execute()
            
            if response.data and len(response.data) > 0:
                problem_file = response.data[0].get('problem_files')
                if problem_file:
                    return problem_file['owner'], problem_file['problem_name']
        
        elif entity_type == 'subtask':
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
    """Get all comments for a specific entity from database"""
    try:
        supabase = get_supabase_client()
        
        response = supabase.table('comments').select('*').eq(
            'entity_type', entity_type
        ).eq('entity_id', entity_id).order('created_at', desc=False).execute()
        
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
    """Display comments section with @mentions support"""
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
    
    # Show comment form with mentions support
    show_comment_form_with_mentions(
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
# ENHANCED COMMENT FORM WITH MENTIONS
# ============================================================================

def show_comment_form_with_mentions(entity_type: str, entity_id: str, entity_name: str,
                                   file_owner: str, file_name: str, can_notify: bool):
    """Display comment form with @mentions support and user selection"""
    
    with st.expander("➕ Add New Comment", expanded=False):
        # Show notification status
        if can_notify:
            owner_email = get_user_email(file_owner)
            st.success(f"📧 Your comment will notify **{file_owner}** at {owner_email}")
        elif file_owner and file_owner != st.session_state.current_user:
            st.warning(f"⚠️ {file_owner} has no email configured - no notification will be sent")
        elif file_owner == st.session_state.current_user:
            st.info("ℹ️ You're commenting on your own file - no email notification needed")
        
        # Initialize comment text in session state if not exists
        comment_key = f"comment_draft_{entity_type}_{entity_id}"
        if comment_key not in st.session_state:
            st.session_state[comment_key] = ""
        
        # Mention selector section
        available_users = get_available_users()
        other_users = [user for user in available_users if user != st.session_state.current_user]
        
        print(f"[DEBUG] Available users: {available_users}")
        print(f"[DEBUG] Current user: {st.session_state.current_user}")
        print(f"[DEBUG] Other users: {other_users}")
        
        if other_users:
            st.markdown("**👥 Mention Someone:**")
            mention_cols = st.columns(len(other_users) + 1)
            
            for i, user in enumerate(other_users):
                with mention_cols[i]:
                    if st.button(f"@{user}", key=f"mention_btn_{user}_{entity_type}_{entity_id}", 
                                help=f"Add @{user} to your comment"):
                        # Add mention to comment text
                        current_text = st.session_state[comment_key]
                        if current_text and not current_text.endswith(' '):
                            current_text += " "
                        st.session_state[comment_key] = current_text + f"@{user} "
                        st.rerun()
            
            # Clear mentions button
            with mention_cols[-1]:
                if st.button("🗑️ Clear", key=f"clear_mentions_{entity_type}_{entity_id}",
                           help="Clear all mentions from comment"):
                    # Remove all @mentions from the text
                    current_text = st.session_state[comment_key]
                    cleaned_text = re.sub(r'@\w+\s*', '', current_text).strip()
                    st.session_state[comment_key] = cleaned_text
                    st.rerun()
        else:
            st.info(f"Debug: No other users found. Available: {available_users}, Current: {st.session_state.current_user}")
        
        # Comment form)
        
        # Comment form
        with st.form(f"comment_form_{entity_type}_{entity_id}", clear_on_submit=True):
            comment_text = st.text_area(
                "Write your comment:",
                value=st.session_state[comment_key],
                placeholder="Share your thoughts... Click the buttons above to mention someone!",
                key=f"comment_input_{entity_type}_{entity_id}",
                help="Use the mention buttons above or type @username manually",
                height=100
            )
            
            # Update session state with current text
            if comment_text != st.session_state[comment_key]:
                st.session_state[comment_key] = comment_text
            
            # Preview mentions if any
            if comment_text:
                mentions = extract_mentions(comment_text)
                if mentions:
                    valid_mentions = validate_mentions(mentions)
                    invalid_mentions = [m for m in mentions if m not in [v.lower() for v in valid_mentions]]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if valid_mentions:
                            st.success(f"✅ Will notify: {', '.join(valid_mentions)}")
                    with col2:
                        if invalid_mentions:
                            st.warning(f"⚠️ Unknown users: {', '.join(invalid_mentions)}")
            
            submitted = st.form_submit_button("💬 Post Comment", use_container_width=True)
            
            if submitted:
                if comment_text and comment_text.strip():
                    # Clear the draft after successful submission
                    st.session_state[comment_key] = ""
                    
                    handle_comment_submission_with_mentions(
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

def handle_comment_submission_with_mentions(comment_text: str, entity_type: str, entity_id: str,
                                           entity_name: str, file_owner: str, file_name: str,
                                           can_notify: bool, is_reply: bool, parent_id: str = None):
    """Handle comment submission with @mentions processing"""
    
    print(f"[COMMENT_SUBMIT] Handling comment submission with mentions")
    print(f"[COMMENT_SUBMIT] Entity: {entity_type}/{entity_id}")
    print(f"[COMMENT_SUBMIT] File Owner: {file_owner}")
    
    # Extract and validate mentions
    mentions = extract_mentions(comment_text)
    valid_mentions = validate_mentions(mentions)
    
    print(f"[MENTIONS] Found mentions: {mentions}")
    print(f"[MENTIONS] Valid mentions: {valid_mentions}")
    
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
        
        # Send file owner notification (existing logic)
        owner_email_sent = False
        if can_notify and file_owner and file_name:
            print(f"[COMMENT_SUBMIT] Attempting to send file owner notification")
            owner_email_sent = send_email_notification(
                file_owner=file_owner,
                commenter=st.session_state.current_user,
                file_name=file_name,
                entity_name=entity_name,
                comment_text=comment_text,
                is_reply=is_reply
            )
        
        # Send mention notifications (new logic)
        mention_count = 0
        if valid_mentions:
            print(f"[MENTIONS] Sending notifications to {len(valid_mentions)} mentioned users")
            send_mention_notifications(
                mentions=valid_mentions,
                commenter=st.session_state.current_user,
                file_name=file_name,
                entity_name=entity_name,
                comment_text=comment_text,
                is_reply=is_reply
            )
            mention_count = len(valid_mentions)
        
        # Show comprehensive success message
        success_parts = []
        if owner_email_sent:
            success_parts.append(f"{file_owner} notified")
        if mention_count > 0:
            success_parts.append(f"{mention_count} user(s) mentioned")
        
        if success_parts:
            notification_text = " and ".join(success_parts)
            st.success(f"✅ {'Reply' if is_reply else 'Comment'} posted! {notification_text}!")
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

# ============================================================================
# HELPER FUNCTIONS (EXISTING)
# ============================================================================

def check_notification_conditions(file_owner: str) -> bool:
    """Check if email notifications should be sent"""
    if not file_owner:
        print(f"[NOTIFICATION] No file owner provided")
        return False
    
    is_other_file = file_owner != st.session_state.current_user
    if not is_other_file:
        print(f"[NOTIFICATION] User commenting on own file, no notification needed")
        return False
    
    owner_email = get_user_email(file_owner)
    has_email = owner_email is not None
    
    print(f"[NOTIFICATION] Owner: {file_owner}, Email: {owner_email}, Can notify: {is_other_file and has_email}")
    return is_other_file and has_email

def send_email_notification(file_owner: str, commenter: str, file_name: str,
                           entity_name: str, comment_text: str, is_reply: bool) -> bool:
    """Send email notification for comment"""
    try:
        print(f"[EMAIL_NOTIFY] Preparing notification for {file_owner}")
        
        owner_email = get_user_email(file_owner)
        if not owner_email:
            print(f"[EMAIL_NOTIFY] No email found for {file_owner}")
            return False
        
        print(f"[EMAIL_NOTIFY] Found email for {file_owner}: {owner_email}")
        
        task_name = f"Reply in {entity_name}" if is_reply else entity_name
        
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
# ENHANCED COMMENT DISPLAY WITH MENTIONS
# ============================================================================

def display_comments_list(entity_comments: dict, entity_type: str, entity_id: str,
                         file_owner: str, file_name: str, entity_name: str):
    """Display list of comments with @mentions highlighting"""
    
    root_comments = {
        cid: comment for cid, comment in entity_comments.items()
        if not comment.get('parent_id')
    }
    
    sorted_comments = sorted(
        root_comments.items(),
        key=lambda x: parse_timestamp(x[1].get('created_at')),
        reverse=True
    )
    
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
    """Display a single comment with @mentions highlighting and its replies"""
    
    if depth > 0:
        cols = st.columns([depth * 0.05, 1])
        container = cols[1]
    else:
        container = st.container()
    
    with container:
        with st.container(border=True):
            col1, col2, col3 = st.columns([0.1, 5, 0.5])
            
            with col1:
                role_badge = get_role_badge(comment.get('user_role', 'User'))
                st.write(role_badge)
            
            with col2:
                user_name = comment.get('user_name') or comment.get('user', 'Unknown')
                timestamp = format_timestamp(comment.get('created_at'))
                st.markdown(f"**{user_name}** · {timestamp}")
                
                # Display comment with @mentions highlighted
                comment_text = comment['text']
                formatted_text = format_comment_with_mentions(comment_text)
                st.markdown(formatted_text, unsafe_allow_html=True)
                
                if st.button("↩️ Reply", key=f"reply_{comment_id}", use_container_width=False):
                    st.session_state[f"replying_to_{comment_id}"] = True
            
            with col3:
                if can_delete_comment(comment):
                    if st.button("🗑️", key=f"delete_{comment_id}", help="Delete comment"):
                        delete_comment_handler(comment_id)
            
            if st.session_state.get(f"replying_to_{comment_id}", False):
                show_reply_form_with_mentions(
                    parent_id=comment_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    file_owner=file_owner,
                    file_name=file_name
                )
        
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

def show_reply_form_with_mentions(parent_id: str, entity_type: str, entity_id: str,
                                 entity_name: str, file_owner: str, file_name: str):
    """Show reply form with @mentions support and user selection"""
    
    can_notify = check_notification_conditions(file_owner)
    
    # Initialize reply text in session state if not exists
    reply_key = f"reply_draft_{parent_id}"
    if reply_key not in st.session_state:
        st.session_state[reply_key] = ""
    
    with st.form(f"reply_form_{parent_id}", clear_on_submit=True):
        if can_notify:
            st.info(f"📧 Your reply will notify {file_owner}")
        
        # Mention selector for replies
        available_users = get_available_users()
        other_users = [user for user in available_users if user != st.session_state.current_user]
        
        if other_users:
            st.markdown("**👥 Mention in Reply:**")
            mention_cols = st.columns(min(len(other_users), 4))  # Limit to 4 columns for space
            
            for i, user in enumerate(other_users[:4]):  # Show max 4 users
                with mention_cols[i]:
                    if st.button(f"@{user}", key=f"reply_mention_{user}_{parent_id}", 
                                help=f"Add @{user} to your reply"):
                        # Add mention to reply text
                        current_text = st.session_state[reply_key]
                        if current_text and not current_text.endswith(' '):
                            current_text += " "
                        st.session_state[reply_key] = current_text + f"@{user} "
                        st.rerun()
        
        reply_text = st.text_area(
            "Write your reply:", 
            value=st.session_state[reply_key],
            key=f"reply_input_{parent_id}",
            placeholder="Your reply... Click buttons above to mention someone!",
            height=80
        )
        
        # Update session state with current text
        if reply_text != st.session_state[reply_key]:
            st.session_state[reply_key] = reply_text
        
        # Preview mentions in reply
        if reply_text:
            mentions = extract_mentions(reply_text)
            if mentions:
                valid_mentions = validate_mentions(mentions)
                if valid_mentions:
                    st.success(f"✅ Will notify: {', '.join(valid_mentions)}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.form_submit_button("Post Reply", use_container_width=True):
                if reply_text and reply_text.strip():
                    # Clear the draft after successful submission
                    st.session_state[reply_key] = ""
                    
                    handle_comment_submission_with_mentions(
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
                # Clear the draft when canceling
                st.session_state[reply_key] = ""
                del st.session_state[f"replying_to_{parent_id}"]
                st.rerun()

# ============================================================================
# UTILITY FUNCTIONS (EXISTING)
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
    """Parse timestamp for sorting"""
    if not timestamp:
        return datetime.min
    
    if isinstance(timestamp, str):
        try:
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            try:
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

# ============================================================================
# DEBUG FUNCTIONS (OPTIONAL)
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
            st.code(f"Available Users: {get_available_users()}")
        
        with col3:
            st.markdown("**Current User:**")
            st.code(f"User: {st.session_state.current_user}")
            st.code(f"Role: {st.session_state.user_role}")
            
            is_different = file_owner != st.session_state.current_user if file_owner else False
            st.code(f"Different User: {is_different}")
            
            owner_email = get_user_email(file_owner) if file_owner else None
            st.code(f"Owner Email: {owner_email or 'None'}")