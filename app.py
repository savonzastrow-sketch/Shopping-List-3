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

# Initialize Session State
if 'df' not in st.session_state:
    st.session_state['df'] = None
if 'needs_save' not in st.session_state:
    st.session_state['needs_save'] = False

# -----------------------
# STYLES (Mobile-First)
# -----------------------
st.markdown("""
<style>
h1 { font-size: 32px !important; text-align: center; }
.item-row {
    display: flex; align-items: center; justify-content: space-between; 
    padding: 12px 5px; border-bottom: 1px solid #eee; min-height: 50px;
}
.save-warning { color: #ff4b4b; font-weight: bold; text-align: center; padding: 10px; border: 1px solid #ff4b4b; border-radius: 10px; margin-bottom: 10px; }
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
        data = sh.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            df = pd.DataFrame(columns=["item", "purchased", "category", "store"])
        
        # --- STABLE ID FIX ---
        # We assign a permanent ID to every row for this session
        df = df.reset_index().rename(columns={'index': 'sid'})
        
        df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        return df
    except:
        return pd.DataFrame(columns=["sid", "item", "purchased", "category", "store"])

def push_to_cloud():
    with st.spinner("Saving to Cloud..."):
        try:
            client = get_client()
            sh = client.open(SHEET_NAME).sheet1
            # We remove the temporary 'sid' column before saving to Google Sheets
            clean_df = st.session_state['df'].drop(columns=['sid'])
            sh.clear()
            sh.append_rows([clean_df.columns.values.tolist()] + clean_df.values.tolist(), value_input_option='USER_ENTERED')
            st.session_state['needs_save'] = False
            st.success("Cloud Updated! ☁️")
        except Exception as e:
            st.error(f"Save Error: {e}")

# -----------------------
# CORE LOGIC: HANDLERS
# -----------------------
# Use the older experimental params for maximum compatibility
try:
    params = st.experimental_get_query_params()
except:
    params = {}

df_state = st.session_state.get('df')

if df_state is not None:
    # TOGGLE by Stable ID (sid)
    if "t" in params:
        sid_to_find = int(params["t"][0])
        mask = df_state['sid'] == sid_to_find
        if mask.any():
            idx = df_state.index[mask].tolist()[0]
            df_state.at[idx, "purchased"] = not df_state.at[idx, "purchased"]
            st.session_state['needs_save'] = True
        st.experimental_set_query_params()
        st.rerun()

    # DELETE by Stable ID (sid)
    if "d" in params:
        sid_to_find = int(params["d"][0])
        st.session_state['df'] = df_state[df_state['sid'] != sid_to_find].reset_index(drop=True)
        st.session_state['needs_save'] = True
        st.experimental_set_query_params()
        st.rerun()

# -----------------------
# APP START
# -----------------------
if st.session_state['df'] is None:
    st.session_state['df'] = load_data()

df = st.session_state['df']

st.markdown("<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)

# Save/Refresh Controls
if st.session_state['needs_save']:
    st.markdown("<div class='save-warning'>⚠️ You have unsaved changes</div>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    if st.button("☁️ Save to Cloud", use_container_width=True): push_to_cloud()
with c2:
    if st.button("🔄 Refresh", use_container_width=True):
        st.session_state['df'] = None
        st.rerun()

# Add Item Form
with st.form("add_form", clear_on_submit=True):
    col_s, col_c = st.columns(2)
    s = col_s.selectbox("Store", STORES)
    c = col_c.selectbox("Category", CATEGORIES)
    i = st.text_input("Item Name")
    if st.form_submit_button("Add Item") and i.strip():
        # Assign the next logical ID
        next_sid = df['sid'].max() + 1 if not df.empty else 0
        new_row = pd.DataFrame([{"sid": next_sid, "item": i.strip(), "purchased": False, "category": c, "store": s}])
        st.session_state['df'] = pd.concat([df, new_row], ignore_index=True)
        st.session_state['needs_save'] = True
        st.rerun()

st.markdown("---")

# Store Tabs
tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        store_items = df[df['store'] == store_name]
        if store_items.empty:
            st.info(f"No items for {store_name}.")
            continue
        
        # Sort unpurchased items to the top
        sorted_group = store_items.sort_values(by="purchased")
        
        for category, group in sorted_group.groupby("category", sort=False):
            st.markdown(f"**{category}**")
            for _, row in group.iterrows():
                # Visuals
                sid = row["sid"]
                emoji = "✅" if row["purchased"] else "🛒"
                item_style = "text-decoration: line-through; color: #888;" if row["purchased"] else "color: #000;"
                
                # HTML Row using the Stable ID (sid)
                item_html = f"""
                <div class='item-row'>
                    <div style='display: flex; align-items: center; flex-grow: 1;'>
                        <a href='?t={sid}' style='text-decoration: none; margin-right: 15px; font-size: 22px;'>{emoji}</a>
                        <span style='{item_style} font-size: 18px;'>{row['item']}</span>
                    </div>
                    <a href='?d={sid}' style='text-decoration: none; font-size: 20px;'>🗑️</a>
                </div>
                """
                st.markdown(item_html, unsafe_allow_html=True)
