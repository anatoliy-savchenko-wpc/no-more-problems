"""
Comments system component with email notifications
"""
import streamlit as st
import uuid
from datetime import datetime
from database import save_comment, delete_comment
from email_handler import send_partner_comment_notification, get_user_email

def show_comments_section(entity_type: str, entity_id: str, entity_name: str, file_owner: str = None, file_name: str = None):
    """Display comments section for tasks and subtasks with email notifications"""
    st.markdown(f"### 💬 Comments for {entity_name}")
    
    # Debug info - REMOVE IN PRODUCTION
    with st.expander("🔍 Debug Info", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**File Owner:** {file_owner}")
            st.write(f"**File Name:** {file_name}")
            st.write(f"**Current User:** {st.session_state.current_user}")
        with col2:
            st.write(f"**User Role:** {st.session_state.user_role}")
            owner_email = get_user_email(file_owner) if file_owner else None
            st.write(f"**Owner Email:** {owner_email if owner_email else 'Not configured'}")
            st.write(f"**Can notify:** {file_owner and file_owner != st.session_state.current_user and owner_email is not None}")
    
    # Check if commenting on someone else's file
    is_commenting_on_other_file = (
        file_owner and 
        file_owner != st.session_state.current_user
    )
    
    # Get comments for this entity
    entity_comments = {}
    for comment_id, comment in st.session_state.data.get('comments', {}).items():
        if comment['entity_type'] == entity_type and comment['entity_id'] == entity_id:
            entity_comments[comment_id] = comment
    
    # Add new comment form
    with st.expander("➕ Add Comment", expanded=False):
        with st.form(f"new_comment_{entity_type}_{entity_id}"):
            comment_text = st.text_area("Your comment:", key=f"comment_text_{entity_type}_{entity_id}")
            
            # Show notification info if commenting on other's file AND email is configured
            if is_commenting_on_other_file:
                owner_email = get_user_email(file_owner) if file_owner else None
                if owner_email:
                    st.info(f"📧 Your comment will notify {file_owner} via email ({owner_email})")
                else:
                    st.warning(f"⚠️ {file_owner} has no email configured - no notification will be sent")
            
            if st.form_submit_button("Post Comment"):
                if comment_text:
                    comment_id = str(uuid.uuid4())
                    comment_data = {
                        'entity_type': entity_type,
                        'entity_id': entity_id,
                        'user_name': st.session_state.current_user,
                        'text': comment_text,
                        'created_at': datetime.now(),
                        'parent_id': None,
                        'user_role': st.session_state.user_role
                    }
                    
                    if save_comment(comment_id, comment_data):
                        st.session_state.data['comments'][comment_id] = comment_data
                        
                        # Send email notification if all conditions are met
                        email_sent = False
                        if is_commenting_on_other_file and file_owner and file_name:
                            try:
                                # Debug output
                                print(f"[COMMENT DEBUG] Attempting to send email notification:")
                                print(f"  - File Owner: {file_owner}")
                                print(f"  - Commenter: {st.session_state.current_user}")
                                print(f"  - File Name: {file_name}")
                                print(f"  - Task/Entity: {entity_name}")
                                
                                # Check if owner has email
                                owner_email = get_user_email(file_owner)
                                if owner_email:
                                    send_partner_comment_notification(
                                        file_owner=file_owner,
                                        partner_name=st.session_state.current_user,
                                        file_name=file_name,
                                        task_name=entity_name,
                                        comment_text=comment_text
                                    )
                                    email_sent = True
                                    print(f"[COMMENT DEBUG] Email notification queued for {owner_email}")
                                else:
                                    print(f"[COMMENT DEBUG] No email found for {file_owner}")
                                    
                            except Exception as e:
                                print(f"[COMMENT ERROR] Failed to send email: {e}")
                                st.error(f"Comment saved but email notification failed: {e}")
                        
                        # Show appropriate success message
                        if email_sent:
                            st.success(f"✅ Comment posted and {file_owner} notified via email!")
                        else:
                            st.success("✅ Comment posted!")
                        
                        st.rerun()
                else:
                    st.error("Please enter a comment.")
    
    # Display existing comments
    if entity_comments:
        display_comments_list(entity_comments, entity_type, entity_id, file_owner, file_name)
    else:
        st.info("No comments yet. Be the first to comment!")

def display_comments_list(entity_comments, entity_type, entity_id, file_owner=None, file_name=None):
    """Display list of comments with threading"""
    # Separate root comments and replies
    root_comments = {cid: c for cid, c in entity_comments.items() if c.get('parent_id') is None}
    
    # Sort by created_at (newest first)
    sorted_comments = sorted(root_comments.items(), key=lambda x: x[1]['created_at'], reverse=True)
    
    for comment_id, comment in sorted_comments:
        display_comment_thread(
            comment_id, 
            comment, 
            entity_comments, 
            entity_type, 
            entity_id, 
            0,
            file_owner,
            file_name
        )

def display_comment_thread(comment_id: str, comment: dict, all_comments: dict, 
                          entity_type: str, entity_id: str, depth: int,
                          file_owner: str = None, file_name: str = None):
    """Display a comment and its replies recursively"""
    
    # Format role badge
    role_badge = {
        'Admin': '👑',
        'Partner': '🤝',
        'User': '👤'
    }.get(comment.get('user_role', 'User'), '👤')
    
    # Create container for comment
    with st.container():
        # Add indentation for nested replies
        if depth > 0:
            st.markdown(f"{'│ ' * depth}")
        
        col1, col2, col3 = st.columns([0.1, 5, 1])
        
        with col1:
            st.write(role_badge)
        
        with col2:
            # Get username with fallback
            user_name = comment.get('user_name') or comment.get('user') or 'Unknown'
            created_at = comment.get('created_at', datetime.now())
            
            # Format the timestamp
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    created_at = datetime.now()
            
            st.markdown(f"**{user_name}** • {created_at.strftime('%Y-%m-%d %H:%M')}")
            st.write(comment['text'])
        
        with col3:
            # Show delete button if user can delete
            user_name = comment.get('user_name') or comment.get('user', '')
            can_delete = (
                user_name == st.session_state.current_user or 
                st.session_state.user_role in ['Admin', 'Partner']
            )
            
            if can_delete:
                if st.button("🗑️", key=f"del_comment_{comment_id}", help="Delete comment"):
                    if delete_comment(comment_id):
                        del st.session_state.data['comments'][comment_id]
                        st.success("Comment deleted!")
                        st.rerun()
        
        # Reply functionality
        handle_reply_functionality(
            comment_id, 
            entity_type, 
            entity_id, 
            file_owner, 
            file_name,
            entity_name=None  # We don't have entity_name here, but replies don't need specific notification
        )
        
        # Display replies recursively
        replies = {cid: c for cid, c in all_comments.items() if c.get('parent_id') == comment_id}
        if replies:
            sorted_replies = sorted(replies.items(), key=lambda x: x[1]['created_at'])
            for reply_id, reply in sorted_replies:
                display_comment_thread(
                    reply_id, 
                    reply, 
                    all_comments, 
                    entity_type, 
                    entity_id, 
                    depth + 1,
                    file_owner,
                    file_name
                )

def handle_reply_functionality(comment_id, entity_type, entity_id, file_owner, file_name, entity_name=None):
    """Handle reply button and form for a comment"""
    
    # Check if we can send email notifications for replies
    is_replying_to_other_file = (
        file_owner and 
        file_owner != st.session_state.current_user
    )
    
    # Reply button
    if st.button(f"↩️ Reply", key=f"reply_btn_{comment_id}"):
        st.session_state[f"replying_to_{comment_id}"] = True
    
    # Show reply form if replying
    if st.session_state.get(f"replying_to_{comment_id}", False):
        with st.form(f"reply_form_{comment_id}"):
            reply_text = st.text_area("Your reply:", key=f"reply_text_{comment_id}")
            
            # Show email notification info for replies
            if is_replying_to_other_file:
                owner_email = get_user_email(file_owner) if file_owner else None
                if owner_email:
                    st.info(f"📧 Your reply will notify {file_owner}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Post Reply"):
                    if reply_text:
                        reply_id = str(uuid.uuid4())
                        reply_data = {
                            'entity_type': entity_type,
                            'entity_id': entity_id,
                            'user_name': st.session_state.current_user,
                            'text': reply_text,
                            'created_at': datetime.now(),
                            'parent_id': comment_id,
                            'user_role': st.session_state.user_role
                        }
                        
                        if save_comment(reply_id, reply_data):
                            st.session_state.data['comments'][reply_id] = reply_data
                            
                            # Send email for replies too
                            email_sent = False
                            if is_replying_to_other_file and file_owner and file_name:
                                try:
                                    owner_email = get_user_email(file_owner)
                                    if owner_email:
                                        send_partner_comment_notification(
                                            file_owner=file_owner,
                                            partner_name=st.session_state.current_user,
                                            file_name=file_name,
                                            task_name=f"Reply in {entity_name or 'discussion'}",
                                            comment_text=reply_text
                                        )
                                        email_sent = True
                                        print(f"[REPLY DEBUG] Email notification sent for reply")
                                except Exception as e:
                                    print(f"[REPLY ERROR] Failed to send email: {e}")
                            
                            st.session_state[f"replying_to_{comment_id}"] = False
                            
                            if email_sent:
                                st.success(f"Reply posted and {file_owner} notified!")
                            else:
                                st.success("Reply posted!")
                            
                            st.rerun()
                    else:
                        st.error("Please enter a reply.")
            
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state[f"replying_to_{comment_id}"] = False
                    st.rerun()