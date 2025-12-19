import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

st.set_page_config(page_title="🛒 Shopping List", layout="centered")

# --- NEW: SHARED SAVE FUNCTION ---
def save_to_cloud(df_to_save):
    """Encapsulates the full-sheet replacement logic."""
    try:
        client = get_client()
        sh = client.open(SHEET_NAME).sheet1
        # Drop the session-only ID and convert everything to strings
        clean_df = df_to_save.drop(columns=['sid']).astype(str)
        sh.clear()
        sh.append_rows([clean_df.columns.values.tolist()] + clean_df.values.tolist(), value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Cloud Sync Failed: {e}")
        return False

# 2. THE HANDLER (Updated with Auto-Save)
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
                # AUTO-SAVE BEFORE RERUN
                save_to_cloud(df)
            st.query_params.clear()
            st.rerun()

        # Delete Logic
        if "d" in params:
            sid = int(params["d"])
            new_df = df[df['sid'] != sid].reset_index(drop=True)
            st.session_state['df'] = new_df
            # AUTO-SAVE BEFORE RERUN
            save_to_cloud(new_df)
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
        df = df.reset_index().rename(columns={'index': 'sid'})
        df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        return df
    except:
        return pd.DataFrame(columns=["sid", "item", "purchased", "category", "store"])

# 4. INITIALIZE DATA
if 'df' not in st.session_state or st.session_state['df'] is None:
    st.session_state['df'] = load_data()

handle_clicks()

# 5. UI DISPLAY
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>🛒 Shopping List</h1>", unsafe_allow_html=True)

st.markdown("""
<style>
    /* Increase font size for the Tabs (Stores) */
    button[data-testid="stMarker"] p {
        font-size: 24px !important;
        font-weight: 600 !important;
    }

    /* Optional: Ensure the tabs stay on one line on mobile */
    div[data-testid="stTab"] {
        min-width: fit-content !important;
    }
</style>
""", unsafe_allow_html=True)

# Action Bar
col_r = st.columns(1)[0] # Only need refresh now since save is automatic
if col_r.button("🔄 Force Refresh from Cloud", use_container_width=True):
    st.session_state['df'] = None
    st.rerun()

st.markdown("---")

# ADD ITEM FORM
with st.expander("➕ Add New Item"):
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        store_choice = c1.selectbox("Store", STORES)
        cat_choice = c2.selectbox("Category", CATEGORIES)
        item_name = st.text_input("Item Name")
        
        if st.form_submit_button("Add to List", use_container_width=True):
            if item_name.strip():
                df = st.session_state['df']
                next_sid = df['sid'].max() + 1 if not df.empty else 0
                new_row = pd.DataFrame([{
                    "sid": next_sid, "item": item_name.strip(), 
                    "purchased": False, "category": cat_choice, "store": store_choice
                }])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                st.session_state['df'] = updated_df
                # AUTO-SAVE FOR ADDITIONS
                save_to_cloud(updated_df)
                st.rerun()

# 6. TABS & LIST
tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        df = st.session_state['df']
        store_items = df[df['store'] == store_name]
        
        if store_items.empty:
            st.info(f"Empty list.")
        else:
            sorted_items = store_items.sort_values("purchased")
            for cat, group in sorted_items.groupby("category", sort=False):
                st.markdown(f"**{cat}**")
                for _, row in group.iterrows():
                    sid = row['sid']
                    emoji = "✅" if row['purchased'] else "🛒"
                    style = ""
                                        
                    # HTML Grid Row for tight mobile spacing
                    st.markdown(f"""
                    <div style='display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid #eee;'>
                        <a href='?t={sid}' target='_self' style='text-decoration: none; font-size: 22px; width: 40px;'>{emoji}</a>
                        <span style='flex-grow: 1; font-size: 18px;'>{row['item']}</span>
                        <a href='?d={sid}' target='_self' style='text-decoration: none; font-size: 20px; width: 40px; text-align: right;'>🗑️</a>
                    </div>
                    """, unsafe_allow_html=True)
