"""
Contact management component
"""
import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
from database import save_contact, delete_contact
from utils import can_manage_contacts

def show_contacts_section(file_id: str, problem_file: dict):
    """Display contacts section for a problem file"""
    st.markdown("### 📇 Contact List")
    
    # Check if user can manage contacts
    can_manage = can_manage_contacts(problem_file['owner'])
    
    # Get contacts for this file
    file_contacts = {}
    for contact_id, contact in st.session_state.data.get('contacts', {}).items():
        if contact['problem_file_id'] == file_id:
            file_contacts[contact_id] = contact
    
    # Add new contact form (only if user can manage)
    if can_manage:
        with st.expander("➕ Add New Contact", expanded=False):
            with st.form(f"new_contact_{file_id}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    contact_name = st.text_input("Name*")
                    organization = st.text_input("Organization")
                    title = st.text_input("Title/Position")
                
                with col2:
                    email = st.text_input("Email")
                    telephone = st.text_input("Telephone")
                    comments = st.text_area("Comments/Notes")
                
                if st.form_submit_button("Add Contact"):
                    if contact_name:
                        contact_id = str(uuid.uuid4())
                        contact_data = {
                            'problem_file_id': file_id,
                            'name': contact_name,
                            'organization': organization,
                            'title': title,
                            'email': email,
                            'telephone': telephone,
                            'comments': comments,
                            'added_by': st.session_state.current_user,
                            'created_at': datetime.now()
                        }
                        
                        if save_contact(contact_id, contact_data):
                            st.session_state.data['contacts'][contact_id] = contact_data
                            st.success("Contact added successfully!")
                            st.rerun()
                    else:
                        st.error("Please enter at least the contact name.")
    
    # Display contacts
    if file_contacts:
        # Create DataFrame for display
        contacts_list = []
        for contact_id, contact in file_contacts.items():
            contacts_list.append({
                'ID': contact_id,
                'Name': contact['name'],
                'Organization': contact.get('organization', ''),
                'Title': contact.get('title', ''),
                'Email': contact.get('email', ''),
                'Telephone': contact.get('telephone', ''),
                'Comments': contact.get('comments', ''),
                'Added By': contact.get('added_by', ''),
                'Added On': contact['created_at'].strftime('%Y-%m-%d')
            })
        
        df_contacts = pd.DataFrame(contacts_list)
        
        # Display contacts table
        st.dataframe(df_contacts.drop('ID', axis=1), use_container_width=True)
        
        # Edit/Delete contacts (only if user can manage)
        if can_manage:
            st.markdown("#### Manage Contacts")
            
            contact_to_manage = st.selectbox(
                "Select contact to edit/delete:",
                options=[None] + list(file_contacts.keys()),
                format_func=lambda x: "Select..." if x is None else file_contacts[x]['name'],
                key=f"manage_contact_{file_id}"
            )
            
            if contact_to_manage:
                contact = file_contacts[contact_to_manage]
                
                with st.form(f"edit_contact_{contact_to_manage}"):
                    st.write(f"**Editing: {contact['name']}**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_name = st.text_input("Name*", value=contact['name'])
                        new_organization = st.text_input("Organization", value=contact.get('organization', ''))
                        new_title = st.text_input("Title/Position", value=contact.get('title', ''))
                    
                    with col2:
                        new_email = st.text_input("Email", value=contact.get('email', ''))
                        new_telephone = st.text_input("Telephone", value=contact.get('telephone', ''))
                        new_comments = st.text_area("Comments/Notes", value=contact.get('comments', ''))
                    
                    col_update, col_delete = st.columns(2)
                    
                    with col_update:
                        if st.form_submit_button("Update Contact"):
                            if new_name:
                                contact['name'] = new_name
                                contact['organization'] = new_organization
                                contact['title'] = new_title
                                contact['email'] = new_email
                                contact['telephone'] = new_telephone
                                contact['comments'] = new_comments
                                
                                if save_contact(contact_to_manage, contact):
                                    st.success("Contact updated!")
                                    st.rerun()
                            else:
                                st.error("Name is required.")
                    
                    with col_delete:
                        if st.form_submit_button("Delete Contact", type="secondary"):
                            if delete_contact(contact_to_manage):
                                del st.session_state.data['contacts'][contact_to_manage]
                                st.success("Contact deleted!")
                                st.rerun()
    else:
        st.info("No contacts added yet.")