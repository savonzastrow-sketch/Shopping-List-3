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

# --- INITIALIZE SESSION STATE ---
# This is our "Cache Memory" that stays live while you use the app
if 'df' not in st.session_state:
    st.session_state['df'] = None
if 'needs_save' not in st.session_state:
    st.session_state['needs_save'] = False

# -----------------------
# STYLES (Your Optimized Mobile Design)
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
/* Visual indicator for unsaved changes */
.save-warning { color: #ff4b4b; font-weight: bold; font-size: 14px; text-align: center; }
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
        df["purchased"] = df["purchased"].astype(bool)
        return sheet, df
    except gspread.SpreadsheetNotFound:
        # (Creation logic omitted for brevity, but kept same as your previous version)
        return None, pd.DataFrame(columns=["timestamp", "item", "purchased", "category", "store"])

def push_to_cloud():
    """Manually saves the current session state to Google Sheets."""
    client = get_gspread_client()
    spreadsheet = client.open(SHEET_NAME)
    sheet = spreadsheet.sheet1
    df = st.session_state['df']
    
    data_to_write = [df.columns.values.tolist()] + df.values.tolist()
    sheet.clear()
    sheet.append_rows(data_to_write, value_input_option='USER_ENTERED')
    st.session_state['needs_save'] = False
    st.success("Cloud Updated! ☁️")

# -----------------------
# APP START
# -----------------------
g_client = get_gspread_client()
if not g_client: st.stop()

# Initial Load into Session State
if st.session_state['df'] is None:
    _, initial_df = load_data_from_gsheet(g_client)
    st.session_state['df'] = initial_df

df = st.session_state['df']

st.markdown("<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)

# =====================================================
# ADD ITEM & SAVE ACTIONS
# =====================================================
with st.container():
    if st.session_state['needs_save']:
        st.markdown("<p class='save-warning'>⚠️ You have unsaved changes</p>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("☁️ Save to Cloud", use_container_width=True):
            push_to_cloud()
    with col_b:
        if st.button("🔄 Refresh from Cloud", use_container_width=True):
            st.session_state['df'] = None
            st.rerun()

st.subheader("Add an Item")
with st.form(key='add_item_form', clear_on_submit=True):
    c1, c2 = st.columns(2)
    new_store = c1.selectbox("Store", STORES, index=None, placeholder="Store...")
    new_cat = c2.selectbox("Category", CATEGORIES, index=None, placeholder="Category...")
    new_item = st.text_input("Item Name", autocomplete="off") 
    
    if st.form_submit_button("Add Item"):
        if new_store and new_cat and new_item:
            new_row = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "item": new_item.strip(), "purchased": False, 
                "category": new_cat, "store": new_store
            }
            st.session_state['df'] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state['needs_save'] = True
            st.rerun()

st.markdown("---")

# =====================================================
# DISPLAY LOGIC (The Mobile Design)
# =====================================================
# Handle Clicks from the Session Memory (Prevents reload/new tab)
query_params = st.query_params
if "toggle" in query_params:
    idx = int(query_params["toggle"])
    st.session_state['df'].at[idx, "purchased"] = not st.session_state['df'].at[idx, "purchased"]
    st.session_state['needs_save'] = True
    st.query_params.clear()
    st.rerun()

if "delete" in query_params:
    idx = int(query_params["delete"])
    st.session_state['df'] = st.session_state['df'].drop(idx).reset_index(drop=True)
    st.session_state['needs_save'] = True
    st.query_params.clear()
    st.rerun()

tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        store_df = df[df['store'] == store_name]
        if store_df.empty:
            st.info("Empty list.")
            continue

        for category, group in store_df.groupby("category"):
            st.markdown(f"**<span style='color: #1f77b4;'>{category}</span>**", unsafe_allow_html=True)
            for idx, row in group.iterrows():
                # We use idx directly from the main df session state
                status_emoji = "✅" if row["purchased"] else "🛒"
                item_style = "text-decoration: line-through; color: #888;" if row["purchased"] else "color: #000;"
                
                # HTML Output (Preserving your optimized design)
                item_html = f"""
                <div class='item-row'>
                    <div style='display: flex; align-items: center; flex-grow: 1;'>
                        <a href='?toggle={idx}' style='text-decoration: none; margin-right: 15px;'>{status_emoji}</a>
                        <span style='font-size: 18px; {item_style}'>{row["item"]}</span>
                    </div>
                    <a href='?delete={idx}' style='text-decoration: none;'>🗑️</a>
                </div>
                """
                st.markdown(item_html, unsafe_allow_html=True)
