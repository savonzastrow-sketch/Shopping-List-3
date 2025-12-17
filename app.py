import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

st.set_page_config(page_title="🛒 Shopping List", layout="centered")

# 2. THE HANDLER (Must be at the top to catch the click immediately)
# We use st.query_params which is the most reliable for modern Streamlit
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
        # Assign IDs that persist for this session
        df = df.reset_index().rename(columns={'index': 'sid'})
        df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        return df
    except:
        return pd.DataFrame(columns=["sid", "item", "purchased", "category", "store"])

# 4. INITIALIZE DATA
if 'df' not in st.session_state or st.session_state['df'] is None:
    st.session_state['df'] = load_data()
    st.session_state['needs_save'] = False

# Run handler after data is initialized
handle_clicks()

# 5. UI DISPLAY
st.markdown("<h1 style='text-align: center;'>🛒 Shopping List</h1>", unsafe_allow_html=True)

if st.session_state.get('needs_save'):
    st.warning("⚠️ Unsaved changes to Cloud")

col_s, col_r = st.columns(2)
if col_s.button("☁️ Save to Cloud", use_container_width=True):
    # Overwrite Cloud Logic
    client = get_client()
    sh = client.open(SHEET_NAME).sheet1
    clean_df = st.session_state['df'].drop(columns=['sid'])
    sh.clear()
    sh.append_rows([clean_df.columns.values.tolist()] + clean_df.values.tolist(), value_input_option='USER_ENTERED')
    st.session_state['needs_save'] = False
    st.rerun()

if col_r.button("🔄 Refresh", use_container_width=True):
    st.session_state['df'] = None
    st.rerun()

# Tabs and List Rendering (Same as your screen)
tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        df = st.session_state['df']
        items = df[df['store'] == store_name].sort_values("purchased")
        
        for cat, group in items.groupby("category", sort=False):
            st.markdown(f"### {cat}")
            for _, row in group.iterrows():
                sid = row['sid']
                emoji = "✅" if row['purchased'] else "🛒"
                style = "text-decoration: line-through; color: gray;" if row['purchased'] else ""
                
                # The clickable row
                st.markdown(f"""
                <div style='display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #eee;'>
                    <span>
                        <a href='?t={sid}' style='text-decoration: none; margin-right: 10px;'>{emoji}</a>
                        <span style='{style}'>{row['item']}</span>
                    </span>
                    <a href='?d={sid}' style='text-decoration: none;'>🗑️</a>
                </div>
                """, unsafe_allow_html=True)
