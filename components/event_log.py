"""
Key Event Log Component for Problem Files
"""
import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, date, timedelta
from database import save_event_log, delete_event_log

def show_event_log_section(file_id, problem_file, can_edit):
    """Display key event log management interface"""
    
    st.subheader("📅 Key Event Log")
    st.write("Track important milestones, decisions, and events for this problem file.")
    
    # Add new event (only if can edit)
    if can_edit:
        with st.expander("➕ Add New Event"):
            with st.form("new_event"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    event_title = st.text_input("Event Title*", placeholder="e.g., Project Kickoff, Milestone Reached, Issue Resolved")
                    event_description = st.text_area("Event Description*", 
                                                    placeholder="Provide detailed information about this event...")
                with col2:
                    event_date = st.date_input("Event Date*", value=date.today())
                    event_category = st.selectbox("Category", [
                        "Milestone", "Decision", "Issue", "Meeting", "Approval", 
                        "Change Request", "Risk", "Other"
                    ])
                
                if st.form_submit_button("Add Event", use_container_width=True):
                    if event_title and event_description:
                        event_id = str(uuid.uuid4())
                        event_data = {
                            'problem_file_id': file_id,
                            'title': event_title,
                            'description': event_description,
                            'event_date': datetime.combine(event_date, datetime.min.time()),
                            'category': event_category,
                            'created_by': st.session_state.current_user,
                            'created_at': datetime.now()
                        }
                        
                        if save_event_log(event_id, event_data):
                            # Add to session state for immediate display
                            if 'event_logs' not in st.session_state.data:
                                st.session_state.data['event_logs'] = {}
                            st.session_state.data['event_logs'][event_id] = event_data
                            st.success(f"Event '{event_title}' added successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to add event.")
                    else:
                        st.error("Please fill in all required fields.")
    
    # Display existing events
    event_logs = get_file_event_logs(file_id)
    
    if not event_logs:
        st.info("No events logged yet. Add your first event above to start tracking key milestones!")
        return
    
    # Sort events by date (newest first)
    sorted_events = sorted(event_logs.items(), 
                          key=lambda x: x[1]['event_date'], reverse=True)
    
    # Display events as cards
    st.write(f"**Total Events:** {len(event_logs)}")
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        category_filter = st.selectbox("Filter by Category", 
                                     ["All"] + ["Milestone", "Decision", "Issue", "Meeting", 
                                               "Approval", "Change Request", "Risk", "Other"])
    with col2:
        date_range = st.selectbox("Date Range", 
                                ["All Time", "Last 30 Days", "Last 90 Days", "This Year"])
    
    # Apply filters
    filtered_events = apply_event_filters(sorted_events, category_filter, date_range)
    
    # Display filtered events
    for event_id, event in filtered_events:
        display_event_card(event_id, event, can_edit, file_id)

def get_file_event_logs(file_id):
    """Get all event logs for a specific problem file"""
    all_events = st.session_state.data.get('event_logs', {})
    return {eid: event for eid, event in all_events.items() 
            if event.get('problem_file_id') == file_id}

def apply_event_filters(events, category_filter, date_range):
    """Apply filters to events list"""
    filtered = events
    
    # Category filter
    if category_filter != "All":
        filtered = [(eid, event) for eid, event in filtered 
                   if event.get('category') == category_filter]
    
    # Date range filter
    if date_range != "All Time":
        cutoff_date = datetime.now()
        if date_range == "Last 30 Days":
            cutoff_date = datetime.now() - timedelta(days=30)
        elif date_range == "Last 90 Days":
            cutoff_date = datetime.now() - timedelta(days=90)
        elif date_range == "This Year":
            cutoff_date = datetime(datetime.now().year, 1, 1)
        
        filtered = [(eid, event) for eid, event in filtered 
                   if event['event_date'] >= cutoff_date]
    
    return filtered

def display_event_card(event_id, event, can_edit, file_id):
    """Display an individual event card"""
    # Category color mapping
    category_colors = {
        "Milestone": "🏆",
        "Decision": "⚖️",
        "Issue": "⚠️",
        "Meeting": "🤝",
        "Approval": "✅",
        "Change Request": "🔄",
        "Risk": "🚨",
        "Other": "📝"
    }
    
    category_icon = category_colors.get(event.get('category', 'Other'), "📝")
    
    with st.container():
        # Create a bordered container
        st.markdown("""
        <style>
        .event-card {
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            padding: 16px;
            margin: 8px 0;
            background-color: #f8f9fa;
        }
        </style>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"**{category_icon} {event['title']}**")
            st.write(event['description'])
            st.caption(f"Created by {event.get('created_by', 'Unknown')} on {event.get('created_at', datetime.now()).strftime('%Y-%m-%d')}")
        
        with col2:
            st.write(f"**Date:** {event['event_date'].strftime('%Y-%m-%d')}")
            st.write(f"**Category:** {event.get('category', 'Other')}")
        
        with col3:
            if can_edit and st.session_state.user_role in ['Admin', 'Partner']:
                if st.button("🗑️ Delete", key=f"delete_event_{event_id}"):
                    if delete_event_log(event_id):
                        if event_id in st.session_state.data.get('event_logs', {}):
                            del st.session_state.data['event_logs'][event_id]
                        st.success("Event deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete event.")
        
        st.markdown("---")

# Database functions (add these to your database.py file)
def save_event_log(event_id: str, event_data: dict):
    """Save an event log entry to Supabase"""
    try:
        from database import init_supabase
        supabase = init_supabase()
        
        db_data = {
            'id': event_id,
            'problem_file_id': event_data['problem_file_id'],
            'title': event_data['title'],
            'description': event_data['description'],
            'event_date': event_data['event_date'].isoformat(),
            'category': event_data['category'],
            'created_by': event_data['created_by'],
            'created_at': event_data['created_at'].isoformat()
        }
        
        supabase.table('event_logs').upsert(db_data).execute()
        return True
        
    except Exception as e:
        st.error(f"Error saving event log: {e}")
        return False

def delete_event_log(event_id: str):
    """Delete an event log entry from Supabase"""
    try:
        from database import init_supabase
        supabase = init_supabase()
        supabase.table('event_logs').delete().eq('id', event_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting event log: {e}")
        return False

def load_event_logs():
    """Load event logs from Supabase (add this to your database.py load_data function)"""
    try:
        from database import init_supabase, safe_parse_date
        supabase = init_supabase()
        events_response = supabase.table('event_logs').select('*').execute()
        
        events = {}
        for event in events_response.data:
            event_id = event['id']
            events[event_id] = {
                'problem_file_id': event['problem_file_id'],
                'title': event['title'],
                'description': event['description'],
                'event_date': safe_parse_date(event['event_date']),
                'category': event['category'],
                'created_by': event['created_by'],
                'created_at': safe_parse_date(event['created_at'])
            }
        
        st.session_state.data['event_logs'] = events
        
    except Exception as e:
        st.error(f"Error loading event logs: {e}")
        st.session_state.data['event_logs'] = {}