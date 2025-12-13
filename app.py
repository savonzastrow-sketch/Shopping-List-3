import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import time

# --- Configuration Constants ---
SHEET_NAME = "Shopping_List_Data"
FOLDER_ID = st.secrets["FOLDER_ID"] # Ensure this secret is set in .streamlit/secrets.toml

# --- Streamlit Page Configuration ---
st.set_page_config(layout="wide")
st.title("🛒 Personal Shopping List")

# --- Helper Functions ---

# Function to get the gspread client securely from Streamlit secrets
@st.cache_resource
def get_gspread_client():
    """Authenticates the service account and returns the gspread client."""
    try:
        # Create a dictionary structure matching the service account JSON
        service_account_info = st.secrets["gcp_service_account"]
        
        # Authenticate and return the client
        client = gspread.service_account_from_dict(service_account_info)
        return client
    except Exception as e:
        st.error(f"Authentication Error: Could not connect to Google Sheets/Drive. Please check your `secrets.toml` file.")
        st.exception(e)
        return None

# Function to load the spreadsheet and sheet data
def get_sheet_data(client):
    """Loads the spreadsheet and returns the main sheet object and data."""
    try:
        spreadsheet = client.open(SHEET_NAME)
        sheet = spreadsheet.sheet1
        
        # Read all records and convert to a pandas DataFrame
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        return sheet, df
        
    except gspread.SpreadsheetNotFound:
        st.warning("Shopping List Data sheet not found. Creating a new one...")
        
        # --- Sheet Creation Logic (from Test App success) ---
        try:
            # Create the spreadsheet explicitly inside the Shared Drive folder
            spreadsheet = client.create(SHEET_NAME, folder_id=FOLDER_ID)
            
            # Grant permission to the service account (though it should have it as 'owner' or via sharing)
            service_account_email = st.secrets["gcp_service_account"]["client_email"]
            spreadsheet.share(service_account_email, role='writer', type='user')
            
            sheet = spreadsheet.sheet1
            # Add header row
            sheet.append_row(["Timestamp", "Item Name", "Quantity", "Notes"])
            
            st.success(f"Successfully created a new sheet named '{SHEET_NAME}' in your Shared Drive.")
            return sheet, pd.DataFrame() # Return empty DataFrame
            
        except Exception as e:
            st.error(f"Failed to create new spreadsheet in the folder (ID: {FOLDER_ID}). Please verify the Service Account has 'Editor'/'Content Manager' permissions on the Shared Drive.")
            st.exception(e)
            return None, pd.DataFrame()

# --- Main Logic ---

# 1. Initialize Client
g_client = get_gspread_client()

if g_client:
    # 2. Get Sheet and Data
    sheet, df_data = get_sheet_data(g_client)

    if sheet is not None:
        
        # --- Interface for Adding Items ---
        st.subheader("Add New Item")

        with st.form(key='item_form', clear_on_submit=True):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                item_name = st.text_input("Item Name", key='item_name')
            with col2:
                quantity = st.text_input("Quantity/Amount", value='1', key='quantity')

            notes = st.text_area("Notes (Optional)", key='notes')

            submit_button = st.form_submit_button(label='Add to List')

        if submit_button:
            if not item_name:
                st.error("Please enter an Item Name.")
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_row = [timestamp, item_name, quantity, notes]
                
                try:
                    # Append the new row to the sheet
                    sheet.append_row(new_row)
                    st.success(f"Successfully added '{item_name}' to the list!")
                    
                    # Refresh data display after successful save
                    st.rerun() 
                    
                except Exception as e:
                    st.error("Could not write data to the Google Sheet. Please check API permissions and Sheet security.")
                    st.exception(e)

        st.divider()

        # --- Display Current Shopping List ---
        st.subheader("Current Shopping List")
        
        if df_data.empty:
            st.info("The shopping list is empty! Add your first item above.")
        else:
            # Drop the 'Timestamp' column for cleaner display
            display_df = df_data.drop(columns=['Timestamp'])
            
            # Display the data in reverse chronological order (newest at the top)
            st.dataframe(display_df.iloc[::-1], use_container_width=True, hide_index=True)
