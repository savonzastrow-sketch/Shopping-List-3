import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# -----------------------
# CONFIG (Google Sheets)
# -----------------------
SHEET_NAME = "Shopping_List_Data"
FOLDER_ID = st.secrets["FOLDER_ID"] 

CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

# -----------------------
# PAGE SETUP
# -----------------------
st.set_page_config(page_title="🛒 Shopping List", layout="centered")

# --- INITIALIZE SESSION STATE (The Cache) ---
if 'df' not in st.session_state:
    st.session_state['df'] = None
if 'needs_save' not in st.session_state:
    st.session_state['needs_save'] = False

# -----------------------
# STYLES (Your Mobile Design)
# -----------------------
st.markdown("""
<style>
h1 { font-size: 32px !important; text-align: center; }
p, div, label, .stMarkdown { font-size: 18px !important; line-height: 1.6; }
.stButton>button { border-radius: 12px; font-weight: 500; }
.item-row {
    display: flex; align-items: center; justify-content: space-between; 
    padding: 8px 5px; margin-bottom: 3px; border-bottom: 1px solid #eee; min-height: 40px;
}
.save-warning { color: #ff4b4b; font-weight: bold; font-size: 14px; text-align: center; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# -----------------------
# DATA FUNCTIONS
# -----------------------
@st.cache_resource
def get_gspread_client():
    try:
        return gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    except Exception as e:
        st.error("Authentication Error.")
        return None

def load_data_from_gsheet(client):
    try:
        spreadsheet = client.open(SHEET_NAME)
        sheet = spreadsheet.sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Ensure column structure
        default_cols = ["timestamp", "item", "purchased", "category", "store"]
        if df.empty or 'store' not in df.columns:
            df = pd.DataFrame(columns=default_cols)
        
        # CRITICAL: Force timestamp and purchased to correct formats immediately
        df["timestamp"] = df["timestamp"].astype(str).str.strip()
        df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        
        return sheet, df
    except Exception:
        return None, pd.DataFrame(columns=["timestamp", "item", "purchased", "category", "store"])

def push_to_cloud():
    """Wipes the Google Sheet and overwrites it with the current Session State."""
    with st.spinner("Overwriting Cloud with your current list..."):
        try:
            client = get_gspread_client()
            spreadsheet = client.open(SHEET_NAME)
            sheet = spreadsheet.sheet1
            df = st.session_state['df']
            
            # Prepare data (headers + rows)
            data_to_write = [df.columns.values.tolist()] + df.values.tolist()
            
            # Wipe and Overwrite
            sheet.clear()
            sheet.append_rows(data_to_write, value_input_option='USER_ENTERED')
            
            st.session_state['needs_save'] = False
            st.success("Cloud Overwritten Successfully! ☁️")
        except Exception as e:
            st.error(f"Save failed: {e}")

# -----------------------
# CORE LOGIC: HANDLERS
# -----------------------
query_params = st.query_params
df_state = st.session_state.get('df')

if df_state is not None and not df_state.empty:
    # Force the dataframe column to be clean strings for comparison
    df_state['timestamp'] = df_state['timestamp'].astype(str).str.strip()

    # TOGGLE HANDLER
    if "toggle" in query_params:
        # Get the ID and fix the URL-encoded space (%20 -> " ")
        t_id = str(query_params["toggle"]).replace("%20", " ").strip()
        
        # Check for an exact match
        mask = df_state['timestamp'] == t_id
        if mask.any():
            idx = df_state.index[mask].tolist()[0]
            df_state.at[idx, "purchased"] = not df_state.at[idx, "purchased"]
            st.session_state['needs_save'] = True
        
        st.query_params.clear()
        st.rerun()

    # DELETE HANDLER
    if "delete" in query_params:
        # Get the ID and fix the URL-encoded space (%20 -> " ")
        t_id = str(query_params["delete"]).replace("%20", " ").strip()
        
        # Only keep items that do NOT match this ID
        if (df_state['timestamp'] == t_id).any():
            st.session_state['df'] = df_state[df_state['timestamp'] != t_id].reset_index(drop=True)
            st.session_state['needs_save'] = True
            
        st.query_params.clear()
        st.rerun()

# -----------------------
# APP START
# -----------------------
g_client = get_gspread_client()
if not g_client: st.stop()

# Initial Load
if st.session_state['df'] is None:
    _, initial_df = load_data_from_gsheet(g_client)
    st.session_state['df'] = initial_df

df = st.session_state['df']

st.markdown("<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)

# --- SAVE & REFRESH BUTTONS ---
with st.container():
    if st.session_state['needs_save']:
        st.markdown("<p class='save-warning'>⚠️ You have unsaved changes</p>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("☁️ Save to Cloud", use_container_width=True):
            push_to_cloud()
    with col_b:
        if st.button("🔄 Refresh List", use_container_width=True):
            st.session_state['df'] = None
            st.query_params.clear()
            st.rerun()

# --- ADD ITEM FORM ---
st.subheader("Add an Item")
with st.form(key='add_item_form', clear_on_submit=True):
    c1, c2 = st.columns(2)
    new_store = c1.selectbox("Store", STORES, index=None, placeholder="Store...")
    new_cat = c2.selectbox("Category", CATEGORIES, index=None, placeholder="Category...")
    new_item = st.text_input("Item Name", autocomplete="off") 
    
    if st.form_submit_button("Add Item"):
        if new_store and new_cat and new_item.strip():
            new_row = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "item": new_item.strip(), "purchased": False, 
                "category": new_cat, "store": new_store
            }
            st.session_state['df'] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state['needs_save'] = True
            st.rerun()

st.markdown("---")

# --- DISPLAY TABS ---
tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        store_df = df[df['store'] == store_name]
        if store_df.empty:
            st.info(f"No items for {store_name}.")
            continue
        
        # Sort unpurchased items to the top
        sorted_df = store_df.sort_values(by="purchased")

        for category, group in sorted_df.groupby("category", sort=False):
            st.markdown(f"**<span style='color: #1f77b4; font-size: 20px;'>{category}</span>**", unsafe_allow_html=True)
            for _, row in group.iterrows():
                t_id = row["timestamp"]
                status_emoji = "✅" if row["purchased"] else "🛒"
                item_style = "text-decoration: line-through; color: #888;" if row["purchased"] else "color: #000;"
                
                item_html = f"""
                <div class='item-row'>
                    <div style='display: flex; align-items: center; flex-grow: 1;'>
                        <a href='?toggle={t_id}' style='text-decoration: none; margin-right: 15px;'>{status_emoji}</a>
                        <span style='font-size: 18px; {item_style}'>{row["item"]}</span>
                    </div>
                    <a href='?delete={t_id}' style='text-decoration: none;'>🗑️</a>
                </div>
                """
                st.markdown(item_html, unsafe_allow_html=True)
