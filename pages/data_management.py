"""
Data management page module
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime
from database import init_supabase, load_data
from utils import can_access_data_management, calculate_project_progress
from auth import get_user_role

def show_data_management():
    """Display data management page"""
    if not can_access_data_management():
        st.error("🚫 Access Denied: Only administrators can access data management.")
        return
    
    st.title("💾 Data Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Export Data")
        
        if st.button("📥 Download All Data (JSON)"):
            data_json = json.dumps(st.session_state.data, indent=2, default=str)
            st.download_button(
                label="Download JSON",
                data=data_json,
                file_name=f"problem_tracker_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        if st.button("📊 Export Summary to CSV"):
            if st.session_state.data['problem_files']:
                summary_data = []
                for file_id, file_data in st.session_state.data['problem_files'].items():
                    progress = calculate_project_progress(file_data['tasks'])
                    
                    # Count comments and contacts
                    file_comments = 0
                    for task_id in file_data['tasks']:
                        file_comments += len([c for c in st.session_state.data.get('comments', {}).values() 
                                            if c['entity_type'] == 'task' and c['entity_id'] == task_id])
                        for subtask_id in file_data['tasks'][task_id]['subtasks']:
                            file_comments += len([c for c in st.session_state.data.get('comments', {}).values() 
                                                if c['entity_type'] == 'subtask' and c['entity_id'] == subtask_id])
                    
                    file_contacts = len([c for c in st.session_state.data.get('contacts', {}).values() 
                                       if c['problem_file_id'] == file_id])
                    
                    summary_data.append({
                        'Problem File': file_data['problem_name'],
                        'Owner': file_data['owner'],
                        'Progress': progress,
                        'Comments': file_comments,
                        'Contacts': file_contacts,
                        'Start Date': file_data['project_start_date'].strftime('%Y-%m-%d'),
                        'Last Modified': file_data['last_modified'].strftime('%Y-%m-%d %H:%M')
                    })
                
                df = pd.DataFrame(summary_data)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"problem_tracker_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    with col2:
        st.subheader("Database Status")
        
        try:
            supabase = init_supabase()
            # Test connection
            test_response = supabase.table('problem_files').select('*').limit(1).execute()
            st.success("✅ Connected to Supabase database")
            
            # Show database stats
            files_count = supabase.table('problem_files').select('*', count='exact').execute()
            tasks_count = supabase.table('tasks').select('*', count='exact').execute()
            subtasks_count = supabase.table('subtasks').select('*', count='exact').execute()
            comments_count = supabase.table('comments').select('*', count='exact').execute()
            contacts_count = supabase.table('contacts').select('*', count='exact').execute()
            
            st.info(f"""📊 Database Stats:
- Problem Files: {files_count.count}
- Tasks: {tasks_count.count}
- Subtasks: {subtasks_count.count}
- Comments: {comments_count.count}
- Contacts: {contacts_count.count}""")
            
        except Exception as e:
            st.error(f"❌ Database connection error: {e}")
    
    st.subheader("User Management")
    
    # Current users with roles
    st.write("**Current Users:**")
    user_data = []
    for user in st.session_state.data['users']:
        role = get_user_role(user)
        role_badge = {
            'Admin': '👑',
            'Partner': '🤝',
            'User': '👤'
        }.get(role, '👤')
        
        user_data.append({
            'User': user,
            'Role': f"{role_badge} {role}",
            'Type': role
        })
    
    df_users = pd.DataFrame(user_data)
    st.dataframe(df_users, use_container_width=True)
    
    st.info("""💡 **User Management Notes**: 
- Update credentials in your Streamlit secrets to add/remove users
- Add user roles in the 'user_roles' section of secrets
- Partners have elevated permissions for collaboration
- Format: username = "role" (Admin/Partner/User)""")
    
    # Refresh data button
    st.subheader("🔄 Data Refresh")
    if st.button("🔄 Refresh Data from Database"):
        load_data()
        st.success("✅ Data refreshed from Supabase!")
        st.rerun()