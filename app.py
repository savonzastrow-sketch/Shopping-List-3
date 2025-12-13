import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import time

# -----------------------
# CONFIG (Google Sheets)
# -----------------------
SHEET_NAME = "Shopping_List_Data"
FOLDER_ID = st.secrets["FOLDER_ID"] 
# Ensure FOLDER_ID and [gcp_service_account] are set in .streamlit/secrets.toml

# Define Categories and Stores
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"] # Store Tabs

# -----------------------
# PAGE SETUP
# -----------------------
st.set_page_config(page_title="🛒 Shopping List", layout="centered")

# --- INITIALIZE SESSION STATE ---
if 'data_version' not in st.session_state:
    st.session_state['data_version'] = 0
if 'g_client' not in st.session_state:
    st.session_state['g_client'] = None

# -----------------------
# STYLES
# -----------------------
st.markdown("""
<style>
h1 { font-size: 32px !important; text-align: center; }
h2 { font-size: 28px !important; text-align: center; }
p, div, label, .stMarkdown { font-size: 18px !important; line-height: 1.6; }

/* General button style */
.stButton>button {
    border-radius: 12px; font-size: 16px; font-weight: 500; transition: all 0.2s ease; padding: 6px 12px;
}

/* Hide the main Streamlit element padding on small screens for max space */
@media (max-width: 480px) {
    /* Target main content padding */
    .st-emotion-cache-1pxx0nch { 
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
}
</style>
""", unsafe_allow_html=True)


# -----------------------
# DATA PERSISTENCE FUNCTIONS
# -----------------------

# Function to get the gspread client securely from Streamlit secrets
@st.cache_resource
def get_gspread_client():
    """Authenticates the service account and returns the gspread client."""
    try:
        service_account_info = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(service_account_info)
        return client
    except Exception as e:
        st.error(f"Authentication Error: Could not connect to Google Sheets/Drive.")
        st.exception(e)
        return None

# The heavy save_data_to_sheet is NO LONGER USED in the new logic
def save_data_to_sheet(sheet, df):
    """Clears the sheet, writes headers, and writes the entire DataFrame. USE SPARINGLY."""
    try:
        sheet.clear()
        sheet.append_row(df.columns.tolist())
        data_to_write = df.values.tolist()
        sheet.append_rows(data_to_write, value_input_option='USER_ENTERED')
    except Exception as e:
        st.error(f"Error saving data to sheet: {e}")

# Function to load the spreadsheet and sheet data
# The argument is prefixed with an underscore to prevent Streamlit cache hashing error
@st.cache_data(ttl=60, show_spinner=False)
def load_and_get_data ( _client, unused_version ) :
    """Loads the spreadsheet, creates it if necessary, and returns the sheet object and DataFrame."""
    try:
        # 1. Open Spreadsheet
        spreadsheet = _client.open(SHEET_NAME) # Corrected reference to _client
        sheet = spreadsheet.sheet1
        
        # 2. Read Data
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 3. Ensure proper dtypes
        if "purchased" in df.columns:
            # Safely convert string representations of booleans
            df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        
        # Reset the index to ensure clean index
        df = df.reset_index(drop=True)
        
        return sheet, df
        
    except gspread.SpreadsheetNotFound:
        st.warning(f"Shopping List Data sheet not found. Creating a new one named '{SHEET_NAME}'...")
        
        # --- Sheet Creation Logic ---
        try:
            # Corrected reference to _client
            spreadsheet = _client.create(SHEET_NAME, folder_id=FOLDER_ID) 
            
            service_account_email = st.secrets["gcp_service_account"]["client_email"]
            spreadsheet.share(service_account_email, role='writer', type='user')
            
            sheet = spreadsheet.sheet1
            sheet.append_row(["timestamp", "item", "purchased", "category", "store"]) 
            
            st.success(f"Successfully created a new sheet in your Shared Drive.")
            df = pd.DataFrame(columns=["timestamp", "item", "purchased", "category", "store"])
            if "purchased" in df.columns:
                df["purchased"] = df["purchased"].astype(bool)
            return sheet, df
            
        except Exception as e:
            st.error(f"FATAL ERROR: Failed to create new spreadsheet in the folder (ID: {FOLDER_ID}).")
            st.exception(e)
            return None, pd.DataFrame(columns=["timestamp", "item", "purchased", "category", "store"])


def find_row_index(sheet, timestamp_id):
    """Finds the 1-based row index in the sheet for a given timestamp."""
    try:
        # Assuming 'timestamp' is the first column (col 1)
        timestamps = sheet.col_values(1)[1:] # [1:] skips the header row
        
        # Find the 0-based index in the list, then add 2 to get the 1-based sheet row index
        index = timestamps.index(timestamp_id)
        return index + 2
    except ValueError:
        st.warning("Item not found in sheet; data may have been updated by another user.")
        return None

# --- NEW CALLBACK FUNCTIONS (EFFICIENT API CALLS - QUOTA FIX) ---
def toggle_item(timestamp_id):
    g_client = st.session_state['g_client']
    sheet, df = load_and_get_data(g_client, st.session_state['data_version'])
    
    # CRITICAL FIX: Check for None sheet object
    if sheet is None:
        st.error("Cannot perform update: Sheet failed to load.")
        return
        
    # Get the current status and calculate new status
    current_status = df.loc[df['timestamp'] == timestamp_id, "purchased"].iloc[0]
    new_status = not current_status
    
    row_index = find_row_index(sheet, timestamp_id)
    
    if row_index:
        # Get the DataFrame column names to find the 1-based index of 'purchased'
        # Note: 'purchased' column is assumed to exist after load_and_get_data
        purchased_col_index = df.columns.get_loc('purchased') + 1
        
        # PERFORM SINGLE CELL UPDATE (CRITICAL FOR QUOTA FIX)
        sheet.update_cell(row_index, purchased_col_index, str(new_status).upper())
        
        # Force reload by incrementing version
        st.session_state['data_version'] += 1

def delete_item(timestamp_id):
    g_client = st.session_state['g_client']
    sheet, df = load_and_get_data(g_client, st.session_state['data_version'])

    # CRITICAL FIX: Check for None sheet object
    if sheet is None:
        st.error("Cannot perform delete: Sheet failed to load.")
        return

    row_index = find_row_index(sheet, timestamp_id)
    
    if row_index:
        # PERFORM SINGLE ROW DELETE (CRITICAL FOR QUOTA FIX)
        sheet.delete_rows(row_index)
        
        # Force reload by incrementing version
        st.session_state['data_version'] += 1

# ----------------------- 
# APP START 
# ----------------------- 
g_client = get_gspread_client() 
st.session_state['g_client'] = g_client # Store client in state

if not g_client:
    st.stop() # Stop execution if authentication fails

# 1. LOAD THE DATA
sheet, df = load_and_get_data(g_client, st.session_state['data_version']) 

if sheet is None:
    st.stop() # Stop if sheet creation/loading failed

st.markdown(f"<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)

# =====================================================
# ADD ITEM FORM (EFFICIENT APPEND LOGIC)
# =====================================================
st.subheader("Add an Item")

with st.form(key='add_item_form', clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        new_store = st.selectbox(
            "Select Store",
            STORES,
            index=None,
            placeholder="Choose a store...",
            key='form_store'
        )

    with col2:
        new_category = st.selectbox(
            "Select Category", 
            CATEGORIES,
            index=None,
            placeholder="Choose a category...",
            key='form_category'
        )
        
    new_item = st.text_input("Enter the item to purchase", autocomplete="off", key='form_item') 
    
    if st.form_submit_button("Add Item"):
        new_item_val = new_item.strip()
        
        # VALIDATION LOGIC
        if not new_store:
            st.warning("Please select a store.")
        elif not new_category:
            st.warning("Please select a category.")
        elif not new_item_val:
            st.warning("Please enter a valid item name.")
        elif new_item_val in df["item"].values:
            st.warning("That item is already on the list.")
        else:
            # APPEND NEW ITEM LOGIC (Uses single sheet.append_row API call)
            new_row = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "item": new_item_val, 
                "purchased": False, 
                "category": new_category,
                "store": new_store
            } 
            
            # The efficient way to add a single item without rewriting the whole sheet
            sheet.append_row(list(new_row.values())) 
            
            st.success(f"'{new_item_val}' added to the list for {new_store} under '{new_category}'.")
            st.session_state['data_version'] += 1 # Increment version to force reload
            st.rerun()

st.markdown("---")
st.subheader("Items by Store")

# =====================================================
# STORE TABS NAVIGATION & DISPLAY (FINAL STABLE VERSION)
# =====================================================

# Check if df is not empty before creating tabs and looping
if not df.empty:
    
    # 1. Create the tabs dynamically
    store_tabs = st.tabs(STORES)
    
    # 2. Loop through the store tabs to display the filtered list in each one
    for store_name, store_tab in zip(STORES, store_tabs):
        with store_tab:
            # 3. Filter the DataFrame for the current store and sort it
            filtered_df = df[df["store"] == store_name].sort_values(
                by=['purchased', 'category', 'item'], ascending=[True, True, True]
            )

            # 4. Loop through the filtered items to display them with the new buttons
            for index, row in filtered_df.iterrows():
                # Ensure timestamp is a string for unique key generation
                timestamp_id = str(row['timestamp'])
                
                # Use a container and columns for alignment
                with st.container():
                    col1, col2, col3, col4 = st.columns([1, 1, 1, 12])
                    
                    # --- TOGGLE BUTTON (Col 1) ---
                    with col1:
                        # Use a form for the button to prevent the new tab issue
                        with st.form(key=f'form_toggle_{timestamp_id}', clear_on_submit=False):
                            toggle_label = "🛒" if row["purchased"] else "✅"
                            # The button calls the new toggle_item function
                            st.form_submit_button(
                                label=toggle_label,
                                on_click=toggle_item,
                                args=(timestamp_id,)
                            )

                    # --- DELETE BUTTON (Col 2) ---
                    with col2:
                        with st.form(key=f'form_delete_{timestamp_id}', clear_on_submit=False):
                            # The button calls the new delete_item function
                            st.form_submit_button(
                                label="🗑️",
                                on_click=delete_item,
                                args=(timestamp_id,)
                            )
                    
                    # --- ITEM DISPLAY (Col 4) ---
                    with col4:
                        # Display item name and quantity with style
                        item_style = "text-decoration: line-through; color: #a0a0a0;" if row["purchased"] else ""
                        st.markdown(f'<span style="{item_style}">{row["item"]}</span>', unsafe_allow_html=True)
