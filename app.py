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

# -----------------------
# STYLES (Includes JavaScript for faster internal rerun)
# -----------------------
# NOTE: The critical JS snippet for fast rerun of links has been modified.
# Streamlit now handles internal query param links better, but we keep the custom 
# style for a better look.

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

/* Custom CSS for the item list layout */
.item-row {
    display: flex; 
    align-items: center; 
    justify-content: space-between; 
    padding: 8px 5px; 
    margin-bottom: 3px; 
    border-bottom: 1px solid #eee; 
    min-height: 40px;
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

# Function to load the spreadsheet and sheet data
def load_and_get_data(client):
    """Loads the spreadsheet, creates it if necessary, and returns the sheet object and DataFrame."""
    try:
        # 1. Open Spreadsheet
        spreadsheet = client.open(SHEET_NAME)
        sheet = spreadsheet.sheet1
        
        # 2. Read Data
        # Use get_all_records() to read data and use the first row as headers
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 3. Ensure proper dtypes
        if "purchased" in df.columns:
            df["purchased"] = df["purchased"].astype(bool)
        
        # IMPORTANT FIX: Reset the index to ensure clean 0, 1, 2... index for toggling/deleting
        df = df.reset_index(drop=True)
        
        return sheet, df
        
    except gspread.SpreadsheetNotFound:
        st.warning(f"Shopping List Data sheet not found. Creating a new one named '{SHEET_NAME}'...")
        
        # --- Sheet Creation Logic (The proven code that works) ---
        try:
            # Create the spreadsheet explicitly inside the Shared Drive folder
            # NOTE: We use the corrected function call without 'share_folder=True'
            spreadsheet = client.create(SHEET_NAME, folder_id=FOLDER_ID) 
            
            # Share with service account (safety check)
            service_account_email = st.secrets["gcp_service_account"]["client_email"]
            spreadsheet.share(service_account_email, role='writer', type='user')
            
            sheet = spreadsheet.sheet1
            # Define header row (must match the keys used in new_row creation)
            sheet.append_row(["timestamp", "item", "purchased", "category", "store"]) 
            
            st.success(f"Successfully created a new sheet in your Shared Drive.")
            # Return a DataFrame with correct columns but no data
            df = pd.DataFrame(columns=["timestamp", "item", "purchased", "category", "store"])
            if "purchased" in df.columns:
                df["purchased"] = df["purchased"].astype(bool)
            return sheet, df
            
        except Exception as e:
            st.error(f"FATAL ERROR: Failed to create new spreadsheet in the folder (ID: {FOLDER_ID}).")
            st.exception(e)
            return None, pd.DataFrame(columns=["timestamp", "item", "purchased", "category", "store"])

def save_data_to_sheet(sheet, df):
    """Writes the entire DataFrame back to the Google Sheet."""
    try:
        # Prepare data: Convert DataFrame to a list of lists (including headers)
        data_to_write = [df.columns.values.tolist()] + df.values.tolist()
        
        # Clear the existing sheet content (including headers)
        sheet.clear()
        
        # Write the new data
        sheet.append_rows(data_to_write, value_input_option='USER_ENTERED')
        
    except Exception as e:
        st.error("Data save failed. Could not write to Google Sheet.")
        st.exception(e)


# -----------------------
# APP START
# -----------------------
g_client = get_gspread_client()

if not g_client:
    st.stop() # Stop execution if authentication fails

sheet, df = load_and_get_data(g_client)

if sheet is None:
    st.stop() # Stop if sheet creation/loading failed

st.markdown(f"<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)


# =====================================================
# ADD ITEM FORM (Outside of tabs so it's always visible)
# =====================================================
st.subheader("Add an Item")

# --- Form Components ---
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
        
        if not new_store:
            st.warning("Please select a store.")
        elif not new_category:
            st.warning("Please select a category.")
        elif not new_item_val:
            st.warning("Please enter a valid item name.")
        elif new_item_val in df["item"].values:
            st.warning("That item is already on the list.")
        else:
            # Save the new item
            new_row = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "item": new_item_val, 
                "purchased": False, 
                "category": new_category,
                "store": new_store
            } 
            
            # Append new row to the DataFrame
            # Note: We append the row to the DataFrame *before* saving the whole sheet
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            # Save the UPDATED DataFrame back to Google Sheets
            save_data_to_sheet(sheet, df)

            st.success(f"'{new_item_val}' added to the list for {new_store} under '{new_category}'.")
            st.rerun()

st.markdown("---")
st.subheader("Items by Store")

# =====================================================
# STORE TABS NAVIGATION & DISPLAY
# =====================================================

# Create the tabs dynamically
store_tabs = st.tabs(STORES)

# Loop through the store tabs to display the filtered list in each one
for store_name, store_tab in zip(STORES, store_tabs):
    with store_tab:
        
        # Filter the main DataFrame for the current store
        df_store = df[df['store'] == store_name]
        
        if df_store.empty:
            st.info(f"The list for **{store_name}** is empty. Add items above!")
            continue # Skip to the next store if the list is empty

        # Group and Sort Items: Group by category, then sort by purchased status within each group
        df_grouped = df_store.sort_values(by=["category", "purchased"])
        
        # Unique categories in the list
        for category, group_df in df_grouped.groupby("category"):
            st.markdown(f"**<span style='font-size: 20px; color: #1f77b4; margin-bottom: 0px !important;'>{category}</span>**", unsafe_allow_html=True)
                       
            for idx, row in group_df.iterrows():
                item_name = row["item"]
                purchased = row["purchased"]

                # 1. Determine the status emoji and style (color only)
                status_emoji = "✅" if purchased else "🛒"
                status_style = "color: #888;" if purchased else "color: #000;"
                
                # 2. Link for the status emoji (to toggle purchase)
                toggle_link = f"<a href='?toggle={idx}' style='text-decoration: none; font-size: 18px; flex-shrink: 0; margin-right: 10px; {status_style}'>{status_emoji}</a>"
                
                # 3. Link for the delete emoji (to delete the item)
                delete_link = f"<a href='?delete={idx}' style='text-decoration: none; font-size: 18px; flex-shrink: 0; color: #f00;'>🗑️</a>"

                # 4. Item Name display (no link)
                item_name_display = f"<span style='font-size: 14px; flex-grow: 1; {status_style}'>{item_name}</span>"

                # 5. Assemble the entire row in a single Markdown block using flexbox
                item_html = f"""
                <div class='item-row'>
                    <div style='display: flex; align-items: center; flex-grow: 1; min-width: 1px;'>
                        {toggle_link}
                        {item_name_display}
                    </div>
                    {delete_link}
                </div>
                """
                st.markdown(item_html, unsafe_allow_html=True)
                
# ----------------------------------------------------
# FINAL CORE LOGIC BLOCK (MUST be placed at the very end of the script)
# This handles the clicks generated by the links and updates the sheet
# ----------------------------------------------------
query_params = st.query_params

# Check for toggle click
toggle_id = query_params.get("toggle", None)
if toggle_id and toggle_id.isdigit():
    clicked_idx = int(toggle_id)
    if clicked_idx in df.index:
        df.loc[clicked_idx, "purchased"] = not df.loc[clicked_idx, "purchased"]
        save_data_to_sheet(sheet, df) # <<< NEW: Save to Google Sheet
        st.query_params.clear() 
        st.rerun()

# Check for delete click
delete_id = query_params.get("delete", None)
if delete_id and delete_id.isdigit():
    clicked_idx = int(delete_id)
    if clicked_idx in df.index:
        df = df.drop(clicked_idx)
        save_data_to_sheet(sheet, df) # <<< NEW: Save to Google Sheet
        st.query_params.clear() 
        st.rerun()
