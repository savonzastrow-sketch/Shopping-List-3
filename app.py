import streamlit as st
import pandas as pd
import gspread

# -----------------------
# CONFIG (Google Sheets)
# -----------------------
SHEET_NAME = "Shopping_List_Data"

CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

# -----------------------
# PAGE SETUP
# -----------------------
st.set_page_config(page_title="🛒 Shopping List", layout="centered")

# --- INITIALIZE SESSION STATE ---
if 'df' not in st.session_state:
    st.session_state['df'] = None
if 'needs_save' not in st.session_state:
    st.session_state['needs_save'] = False

# -----------------------
# STYLES
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
    except Exception:
        return None

def load_data_from_gsheet(client):
    try:
        spreadsheet = client.open(SHEET_NAME)
        sheet = spreadsheet.sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        default_cols = ["item", "purchased", "category", "store"]
        if df.empty or 'item' not in df.columns:
            df = pd.DataFrame(columns=default_cols)
        
        df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        return sheet, df
    except Exception:
        return None, pd.DataFrame(columns=["item", "purchased", "category", "store"])

def push_to_cloud():
    with st.spinner("Saving to Cloud..."):
        try:
            client = get_gspread_client()
            spreadsheet = client.open(SHEET_NAME)
            sheet = spreadsheet.sheet1
            df = st.session_state['df']
            data_to_write = [df.columns.values.tolist()] + df.values.tolist()
            sheet.clear()
            sheet.append_rows(data_to_write, value_input_option='USER_ENTERED')
            st.session_state['needs_save'] = False
            st.success("Cloud Updated! ☁️")
        except Exception as e:
            st.error(f"Save failed: {e}")

# -----------------------
# CORE LOGIC: HANDLERS
# -----------------------
try:
    params = st.experimental_get_query_params()
except AttributeError:
    params = {}

df_state = st.session_state.get('df')

if df_state is not None and not df_state.empty:
    # --- TOGGLE HANDLER ---
    if "toggle_item" in params and "toggle_store" in params:
        # Get and clean the inputs from the URL
        t_item = str(params["toggle_item"][0]).strip().lower()
        t_store = str(params["toggle_store"][0]).strip().lower()
        
        # Create 'fuzzy' columns for a one-time comparison
        temp_items = df_state['item'].astype(str).str.strip().str.lower()
        temp_stores = df_state['store'].astype(str).str.strip().str.lower()
        
        mask = (temp_items == t_item) & (temp_stores == t_store)
        
        if mask.any():
            idx = df_state.index[mask].tolist()[0]
            df_state.at[idx, "purchased"] = not df_state.at[idx, "purchased"]
            st.session_state['needs_save'] = True
        
        st.experimental_set_query_params() 
        st.rerun()

    # --- DELETE HANDLER ---
    if "del_item" in params and "del_store" in params:
        d_item = str(params["del_item"][0]).strip().lower()
        d_store = str(params["del_store"][0]).strip().lower()
        
        temp_items = df_state['item'].astype(str).str.strip().str.lower()
        temp_stores = df_state['store'].astype(str).str.strip().str.lower()
        
        mask = (temp_items == d_item) & (temp_stores == d_store)
        
        if mask.any():
            st.session_state['df'] = df_state[~mask].reset_index(drop=True)
            st.session_state['needs_save'] = True
            
        st.experimental_set_query_params()
        st.rerun()

# -----------------------
# APP START
# -----------------------
g_client = get_gspread_client()
if not g_client: st.stop()

if st.session_state['df'] is None:
    _, initial_df = load_data_from_gsheet(g_client)
    st.session_state['df'] = initial_df

df = st.session_state['df']

st.markdown("<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)

# --- SAVE & REFRESH ---
if st.session_state['needs_save']:
    st.markdown("<p class='save-warning'>⚠️ Unsaved changes</p>", unsafe_allow_html=True)

col_a, col_b = st.columns(2)
with col_a:
    if st.button("☁️ Save to Cloud", use_container_width=True):
        push_to_cloud()
with col_b:
    if st.button("🔄 Refresh", use_container_width=True):
        st.session_state['df'] = None
        st.experimental_set_query_params()
        st.rerun()

# --- ADD ITEM ---
st.subheader("Add Item")
with st.form(key='add_form', clear_on_submit=True):
    c1, c2 = st.columns(2)
    new_store = c1.selectbox("Store", STORES, index=None)
    new_cat = c2.selectbox("Category", CATEGORIES, index=None)
    new_item = st.text_input("Item Name")
    if st.form_submit_button("Add"):
        if new_store and new_cat and new_item.strip():
            new_row = {"item": new_item.strip(), "purchased": False, "category": new_cat, "store": new_store}
            st.session_state['df'] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state['needs_save'] = True
            st.rerun()

st.markdown("---")

# --- DISPLAY ---
tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        store_df = df[df['store'] == store_name]
        if store_df.empty:
            st.info("Empty")
            continue
        
        # Unpurchased at the top
        sorted_df = store_df.sort_values(by="purchased")
        
        for category, group in sorted_df.groupby("category", sort=False):
            st.markdown(f"**<span style='color: #1f77b4;'>{category}</span>**", unsafe_allow_html=True)
            for _, row in group.iterrows():
                name = row["item"]
                emoji = "✅" if row["purchased"] else "🛒"
                style = "text-decoration: line-through; color: #888;" if row["purchased"] else "color: #000;"
                
                # Combine Item and Store in the URL to ensure uniqueness
                html = f"""
                <div class='item-row'>
                    <div style='display: flex; align-items: center; flex-grow: 1;'>
                        <a href='?toggle_item={name}&toggle_store={store_name}' style='text-decoration: none; margin-right: 15px;'>{emoji}</a>
                        <span style='{style}'>{name}</span>
                    </div>
                    <a href='?del_item={name}&del_store={store_name}' style='text-decoration: none;'>🗑️</a>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)
