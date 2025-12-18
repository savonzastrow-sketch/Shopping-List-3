import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

st.set_page_config(page_title="🛒 Shopping List", layout="centered")

# --- THE FIX: Custom CSS to "Lock" columns and style buttons ---
st.markdown("""
<style>
    /* Force columns to stay in a row on mobile (No Stacking) */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
    }
    /* Strip button styles to make them look like simple emoji links */
    div[data-testid="stColumn"] button {
        border: none !important;
        background: transparent !important;
        padding: 0 !important;
        font-size: 22px !important;
        box-shadow: none !important;
        color: inherit !important;
    }
    .item-text { font-size: 18px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    h1 { text-align: center; font-size: 28px !important; }
</style>
""", unsafe_allow_html=True)

# 2. DATA FUNCTIONS
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
        # Use existing 'sid' if present, otherwise create it
        if 'sid' not in df.columns:
            df = df.reset_index().rename(columns={'index': 'sid'})
        df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        return df
    except:
        return pd.DataFrame(columns=["sid", "item", "purchased", "category", "store"])

# 3. INITIALIZE STATE
if 'df' not in st.session_state or st.session_state['df'] is None:
    st.session_state['df'] = load_data()
    st.session_state['needs_save'] = False

# 4. UI DISPLAY
st.markdown("<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)

# Save/Refresh Buttons
col_s, col_r = st.columns(2)
if col_s.button("☁️ Save to Cloud", use_container_width=True):
    try:
        client = get_client()
        sh = client.open(SHEET_NAME).sheet1
        # Convert to strings to avoid JSON errors
        clean_df = st.session_state['df'].drop(columns=['sid']).astype(str)
        sh.clear()
        sh.append_rows([clean_df.columns.values.tolist()] + clean_df.values.tolist(), value_input_option='USER_ENTERED')
        st.session_state['needs_save'] = False
        st.success("Cloud Updated!")
        st.rerun()
    except Exception as e:
        st.error(f"Save failed: {e}")

if col_r.button("🔄 Refresh", use_container_width=True):
    st.session_state['df'] = None
    st.rerun()

if st.session_state['needs_save']:
    st.warning("⚠️ Unsaved changes")

st.markdown("---")

# ADD ITEM FORM
with st.form("add_form", clear_on_submit=True):
    st.subheader("Add New Item")
    c1, c2 = st.columns(2)
    s_choice = c1.selectbox("Store", STORES)
    c_choice = c2.selectbox("Category", CATEGORIES)
    i_name = st.text_input("Item Name")
    if st.form_submit_button("Add Item", use_container_width=True):
        if i_name.strip():
            df = st.session_state['df']
            next_sid = df['sid'].max() + 1 if not df.empty else 0
            new_row = pd.DataFrame([{"sid": next_sid, "item": i_name.strip(), "purchased": False, "category": c_choice, "store": s_choice}])
            st.session_state['df'] = pd.concat([df, new_row], ignore_index=True)
            st.session_state['needs_save'] = True
            st.rerun()

st.markdown("---")

# 5. TABS & LIST
tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        df = st.session_state['df']
        items = df[df['store'] == store_name]
        
        if items.empty:
            st.info("No items.")
        else:
            sorted_items = items.sort_values("purchased")
            for cat, group in sorted_items.groupby("category", sort=False):
                st.markdown(f"**{cat}**")
                for _, row in group.iterrows():
                    sid = row['sid']
                    emoji = "✅" if row['purchased'] else "🛒"
                    style = "text-decoration: line-through; color: gray;" if row['purchased'] else ""
                    
                    # --- NATIVE ROW WITH FLEX LOCK ---
                    # We use very small columns for the icons and most space for the text
                    cols = st.columns([1, 8, 1])
                    
                    # Toggle Button
                    if cols[0].button(emoji, key=f"t_{sid}"):
                        idx = df.index[df['sid'] == sid].tolist()[0]
                        st.session_state['df'].at[idx, "purchased"] = not row["purchased"]
                        st.session_state['needs_save'] = True
                        st.rerun()
                    
                    # Text display
                    cols[1].markdown(f"<div class='item-text' style='{style}'>{row['item']}</div>", unsafe_allow_html=True)
                    
                    # Delete Button
                    if cols[2].button("🗑️", key=f"d_{sid}"):
                        st.session_state['df'] = df[df['sid'] != sid].reset_index(drop=True)
                        st.session_state['needs_save'] = True
                        st.rerun()
