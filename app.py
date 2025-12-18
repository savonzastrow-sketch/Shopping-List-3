# Back-up version- Fully working app, good UI, and save function working (session state is clearing past entries after every button push)

import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

st.set_page_config(page_title="🛒 Shopping List", layout="centered")

# 2. THE HANDLER (Must stay at the top)
params = st.query_params

def handle_clicks():
    if 'df' in st.session_state and st.session_state['df'] is not None:
        df = st.session_state['df']
        
        # Toggle Logic
        if "t" in params:
            sid = int(params["t"])
            mask = df['sid'] == sid
            if mask.any():
                idx = df.index[mask].tolist()[0]
                df.at[idx, "purchased"] = not df.at[idx, "purchased"]
                st.session_state['needs_save'] = True
            st.query_params.clear()
            st.rerun()

        # Delete Logic
        if "d" in params:
            sid = int(params["d"])
            st.session_state['df'] = df[df['sid'] != sid].reset_index(drop=True)
            st.session_state['needs_save'] = True
            st.query_params.clear()
            st.rerun()

# 3. DATA FUNCTIONS
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
        # Assign unique IDs for this session
        df = df.reset_index().rename(columns={'index': 'sid'})
        df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        return df
    except:
        return pd.DataFrame(columns=["sid", "item", "purchased", "category", "store"])

# 4. INITIALIZE DATA
if 'df' not in st.session_state or st.session_state['df'] is None:
    st.session_state['df'] = load_data()
    st.session_state['needs_save'] = False

handle_clicks()

# 5. UI DISPLAY
st.markdown("<h1 style='text-align: center;'>🛒 Shopping List</h1>", unsafe_allow_html=True)

# Save/Refresh Buttons
col_s, col_r = st.columns(2)
if col_s.button("☁️ Save to Cloud", use_container_width=True):
    try:
        client = get_client()
        sh = client.open(SHEET_NAME).sheet1
        # Convert to strings to prevent InvalidJSONError
        clean_df = st.session_state['df'].drop(columns=['sid']).astype(str)
        sh.clear()
        sh.append_rows([clean_df.columns.values.tolist()] + clean_df.values.tolist(), value_input_option='USER_ENTERED')
        st.session_state['needs_save'] = False
        st.success("Saved to Cloud!")
        st.rerun()
    except Exception as e:
        st.error(f"Save failed: {e}")

if col_r.button("🔄 Refresh", use_container_width=True):
    st.session_state['df'] = None
    st.rerun()

if st.session_state.get('needs_save'):
    st.warning("⚠️ Unsaved changes")

st.markdown("---")

# ADD ITEM FORM
st.subheader("Add New Item")
with st.form("add_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    store_choice = c1.selectbox("Store", STORES)
    cat_choice = c2.selectbox("Category", CATEGORIES)
    item_name = st.text_input("What do you need?")
    
    if st.form_submit_button("Add to List", use_container_width=True):
        if item_name.strip():
            df = st.session_state['df']
            next_sid = df['sid'].max() + 1 if not df.empty else 0
            new_row = pd.DataFrame([{
                "sid": next_sid, 
                "item": item_name.strip(), 
                "purchased": False, 
                "category": cat_choice, 
                "store": store_choice
            }])
            st.session_state['df'] = pd.concat([df, new_row], ignore_index=True)
            st.session_state['needs_save'] = True
            st.rerun()

st.markdown("---")

# 6. TABS & LIST
tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        df = st.session_state['df']
        store_items = df[df['store'] == store_name]
        
        if store_items.empty:
            st.info(f"Your {store_name} list is empty.")
        else:
            sorted_items = store_items.sort_values("purchased")
            for cat, group in sorted_items.groupby("category", sort=False):
                st.markdown(f"### {cat}")
                for _, row in group.iterrows():
                    sid = row['sid']
                    emoji = "✅" if row['purchased'] else "🛒"
                    style = "text-decoration: line-through; color: gray;" if row['purchased'] else "font-weight: 500;"
                    
                    # --- THE FIX: Added target='_self' to both <a> tags ---
                    st.markdown(f"""
                    <div style='display: flex; justify-content: space-between; align-items: center; padding: 12px 5px; border-bottom: 1px solid #eee;'>
                        <span style='font-size: 18px;'>
                            <a href='?t={sid}' target='_self' style='text-decoration: none; margin-right: 15px;'>{emoji}</a>
                            <span style='{style}'>{row['item']}</span>
                        </span>
                        <a href='?d={sid}' target='_self' style='text-decoration: none; font-size: 20px;'>🗑️</a>
                    </div>
                    """, unsafe_allow_html=True)
