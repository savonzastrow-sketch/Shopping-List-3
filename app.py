import streamlit as st
import pandas as pd
import gspread

# -----------------------
# CONFIG & SETUP
# -----------------------
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

st.set_page_config(page_title="🛒 Shopping List", layout="centered")

if 'df' not in st.session_state:
    st.session_state['df'] = None
if 'needs_save' not in st.session_state:
    st.session_state['needs_save'] = False

# -----------------------
# STYLES (Preserving your mobile row)
# -----------------------
st.markdown("""
<style>
h1 { font-size: 32px !important; text-align: center; }
.item-row {
    display: flex; align-items: center; justify-content: space-between; 
    padding: 10px 5px; border-bottom: 1px solid #eee; min-height: 45px;
}
.save-warning { color: #ff4b4b; font-weight: bold; text-align: center; padding: 10px; }
</style>
""", unsafe_allow_html=True)

# -----------------------
# DATA ENGINE
# -----------------------
@st.cache_resource
def get_client():
    return gspread.service_account_from_dict(st.secrets["gcp_service_account"])

def load_data():
    try:
        client = get_client()
        sh = client.open(SHEET_NAME).sheet1
        df = pd.DataFrame(sh.get_all_records())
        if df.empty:
            df = pd.DataFrame(columns=["item", "purchased", "category", "store"])
        df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        return df
    except:
        return pd.DataFrame(columns=["item", "purchased", "category", "store"])

def save_to_gsheet():
    try:
        client = get_client()
        sh = client.open(SHEET_NAME).sheet1
        df = st.session_state['df']
        sh.clear()
        sh.append_rows([df.columns.values.tolist()] + df.values.tolist(), value_input_option='USER_ENTERED')
        st.session_state['needs_save'] = False
        st.success("Cloud Updated! ☁️")
    except Exception as e:
        st.error(f"Save Error: {e}")

# -----------------------
# THE HANDLER (The "Scheduling App" logic)
# -----------------------
# Using the index makes this 100% accurate regardless of naming/spaces
params = st.experimental_get_query_params()
df_state = st.session_state.get('df')

if df_state is not None:
    if "t" in params: # 't' for Toggle
        idx = int(params["t"][0])
        if idx in df_state.index:
            df_state.at[idx, "purchased"] = not df_state.at[idx, "purchased"]
            st.session_state['needs_save'] = True
        st.experimental_set_query_params()
        st.rerun()

    if "d" in params: # 'd' for Delete
        idx = int(params["d"][0])
        if idx in df_state.index:
            st.session_state['df'] = df_state.drop(idx).reset_index(drop=True)
            st.session_state['needs_save'] = True
        st.experimental_set_query_params()
        st.rerun()

# -----------------------
# UI & DISPLAY
# -----------------------
if st.session_state['df'] is None:
    st.session_state['df'] = load_data()

df = st.session_state['df']

st.markdown("<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)

if st.session_state['needs_save']:
    st.markdown("<div class='save-warning'>⚠️ You have unsaved changes</div>", unsafe_allow_html=True)

c_save, c_ref = st.columns(2)
with c_save:
    if st.button("☁️ Save to Cloud", use_container_width=True): save_to_gsheet()
with c_ref:
    if st.button("🔄 Refresh", use_container_width=True):
        st.session_state['df'] = None
        st.rerun()

# Add Item Form
with st.form("add_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    s = col1.selectbox("Store", STORES)
    c = col2.selectbox("Category", CATEGORIES)
    i = st.text_input("Item Name")
    if st.form_submit_button("Add Item") and i:
        new_row = pd.DataFrame([{"item": i, "purchased": False, "category": c, "store": s}])
        st.session_state['df'] = pd.concat([df, new_row], ignore_index=True)
        st.session_state['needs_save'] = True
        st.rerun()

# Tabs for Stores
tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        # We use the index from the ORIGINAL dataframe so the buttons work
        store_items = df[df['store'] == store_name]
        
        for category, group in store_items.groupby("category", sort=False):
            st.markdown(f"**{category}**")
            for idx, row in group.iterrows():
                emoji = "✅" if row["purchased"] else "🛒"
                decoration = "line-through" if row["purchased"] else "none"
                color = "#888" if row["purchased"] else "#000"
                
                # HTML Row (Index-based links)
                html = f"""
                <div class='item-row'>
                    <div style='display: flex; align-items: center; flex-grow: 1;'>
                        <a href='?t={idx}' style='text-decoration: none; margin-right: 15px; font-size: 20px;'>{emoji}</a>
                        <span style='text-decoration: {decoration}; color: {color}; font-size: 18px;'>{row['item']}</span>
                    </div>
                    <a href='?d={idx}' style='text-decoration: none; font-size: 20px;'>🗑️</a>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)
