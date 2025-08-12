"""
Comments system component with email notifications for partner comments
"""
import streamlit as st
import uuid
from datetime import datetime
from database import save_comment, delete_comment
from email_handler import send_partner_comment_notification

def show_comments_section(entity_type: str, entity_id: str, entity_name: str, file_owner: str = None, file_name: str = None):
    """Display comments section for tasks and subtasks"""
    st.markdown(f"### 💬 Comments for {entity_name}")

    # Debug info - remove this after testing
    st.write(f"DEBUG - File Owner: {file_owner}, Current User: {st.session_state.current_user}, File Name: {file_name}")

    # Check if current user is a partner commenting on someone else's file
    # New logic (Anyone except owner):
    is_commenting_on_other_file = (
        file_owner and 
        file_owner != st.session_state.current_user
    )

    st.write(f"DEBUG - Is commenting on other's file: {is_commenting_on_other_file}")
    
    # Get comments for this entity
    entity_comments = {}
    for comment_id, comment in st.session_state.data.get('comments', {}).items():
        if comment['entity_type'] == entity_type and comment['entity_id'] == entity_id:
            entity_comments[comment_id] = comment
    
    # Add new comment form
    with st.expander("➕ Add Comment", expanded=False):
        with st.form(f"new_comment_{entity_type}_{entity_id}"):
            comment_text = st.text_area("Your comment:", key=f"comment_text_{entity_type}_{entity_id}")
            
            # Show notification info if partner commenting on other's file
            if is_commenting_on_other_file:
                st.info(f"📧 Your comment will notify {file_owner} via email")
            
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
                        
                        # Send email if partner commenting on other's file
                        if is_commenting_on_other_file and file_name:
                            send_partner_comment_notification(
                                file_owner=file_owner,
                                partner_name=st.session_state.current_user,
                                file_name=file_name,
                                task_name=entity_name,
                                comment_text=comment_text
                            )
                            st.success("Comment posted and owner notified via email!")
                        else:
                            st.success("Comment posted!")
                        
                        st.rerun()
                else:
                    st.error("Please enter a comment.")
    
    # Display comments with threading
    if entity_comments:
        # Separate root comments and replies
        root_comments = {cid: c for cid, c in entity_comments.items() if c.get('parent_id') is None}
        
        # Sort by created_at (newest first)
        sorted_comments = sorted(root_comments.items(), key=lambda x: x[1]['created_at'], reverse=True)
        
        for comment_id, comment in sorted_comments:
            display_comment_thread(comment_id, comment, entity_comments, entity_type, entity_id, 0)
    else:
        st.info("No comments yet. Be the first to comment!")

def display_comment_thread(comment_id: str, comment: dict, all_comments: dict, entity_type: str, entity_id: str, depth: int):
    """Display a comment and its replies recursively"""
    # Add indentation for nested replies
    indent = "  " * depth
    
    # Format role badge
    role_badge = {
        'Admin': '👑',
        'Partner': '🤝',
        'User': '👤'
    }.get(comment.get('user_role', 'User'), '👤')
    
    # Create container for comment
    with st.container():
        if depth > 0:
            st.markdown(f"{'│ ' * depth}")
        
        col1, col2, col3 = st.columns([0.1, 5, 1])
        
        with col1:
            st.write(role_badge)
        
        with col2:
            # Use user_name if available, otherwise fall back to user
            user_name = comment.get('user_name', comment.get('user', 'Unknown'))
            st.markdown(f"**{user_name}** • {comment['created_at'].strftime('%Y-%m-%d %H:%M')}")
            st.write(comment['text'])
        
        with col3:
            # Show delete button if user can delete
            user_name = comment.get('user_name', comment.get('user', ''))
            if (user_name == st.session_state.current_user or 
                st.session_state.user_role in ['Admin', 'Partner']):
                if st.button("🗑️", key=f"del_comment_{comment_id}"):
                    if delete_comment(comment_id):
                        del st.session_state.data['comments'][comment_id]
                        st.rerun()
        
        # Reply button
        if st.button(f"↩️ Reply", key=f"reply_btn_{comment_id}"):
            st.session_state[f"replying_to_{comment_id}"] = True
        
        # Show reply form if replying
        if st.session_state.get(f"replying_to_{comment_id}", False):
            with st.form(f"reply_form_{comment_id}"):
                reply_text = st.text_area("Your reply:", key=f"reply_text_{comment_id}")
                
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
                                st.session_state[f"replying_to_{comment_id}"] = False
                                st.success("Reply posted!")
                                st.rerun()
                        else:
                            st.error("Please enter a reply.")
                
                with col2:
                    if st.form_submit_button("Cancel"):
                        st.session_state[f"replying_to_{comment_id}"] = False
                        st.rerun()
        
        # Display replies
        replies = {cid: c for cid, c in all_comments.items() if c.get('parent_id') == comment_id}
        if replies:
            sorted_replies = sorted(replies.items(), key=lambda x: x[1]['created_at'])
            for reply_id, reply in sorted_replies:
                display_comment_thread(reply_id, reply, all_comments, entity_type, entity_id, depth + 1)