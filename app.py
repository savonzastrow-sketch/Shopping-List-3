import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

# Set to 'centered' but we will override the width with CSS for mobile
st.set_page_config(page_title="🛒 Shopping List", layout="centered")

# --- THE PORTRAIT FIX: Custom Responsive CSS ---
st.markdown("""
<style>
    /* 1. Limit width on desktop but fill 100% on mobile portrait */
    .block-container {
        max-width: 450px !important;
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* 2. Force the item row to stay horizontal even in portrait */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 10px !important;
    }

    /* 3. Thumb-friendly buttons */
    div[data-testid="stColumn"] button {
        border: none !important;
        background: transparent !important;
        padding: 5px !important;
        font-size: 24px !important;
        min-width: 45px !important;
        min-height: 45px !important;
    }

    /* 4. Text styling for vertical reading */
    .item-text {
        font-size: 18px;
        line-height: 1.2;
        word-wrap: break-word;
        flex-grow: 1;
    }
    
    h1 { text-align: center; font-size: 26px !important; margin-bottom: 0px !important; }
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
        # Ensure 'sid' exists for session stability
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

# 4. APP HEADER & UI
st.markdown("<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)

# Main Controls
c_save, c_ref = st.columns(2)
if c_save.button("☁️ Save Cloud", use_container_width=True):
    try:
        client = get_client()
        sh = client.open(SHEET_NAME).sheet1
        clean_df = st.session_state['df'].drop(columns=['sid']).astype(str)
        sh.clear()
        sh.append_rows([clean_df.columns.values.tolist()] + clean_df.values.tolist(), value_input_option='USER_ENTERED')
        st.session_state['needs_save'] = False
        st.success("Synced! ✅")
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

if c_ref.button("🔄 Refresh", use_container_width=True):
    st.session_state['df'] = None
    st.rerun()

if st.session_state['needs_save']:
    st.markdown("<p style='text-align:center; color:red; font-size:12px;'>⚠️ Unsaved changes</p>", unsafe_allow_html=True)

# ADD ITEM FORM
with st.expander("➕ Add New Item", expanded=False):
    with st.form("add_form", clear_on_submit=True):
        s_choice = st.selectbox("Store", STORES)
        c_choice = st.selectbox("Category", CATEGORIES)
        i_name = st.text_input("Item Name")
        if st.form_submit_button("Add to List", use_container_width=True):
            if i_name.strip():
                df = st.session_state['df']
                next_sid = df['sid'].max() + 1 if not df.empty else 0
                new_row = pd.DataFrame([{"sid": next_sid, "item": i_name.strip(), "purchased": False, "category": c_choice, "store": s_choice}])
                st.session_state['df'] = pd.concat([df, new_row], ignore_index=True)
                st.session_state['needs_save'] = True
                st.rerun()

# 5. TABS & LIST
tabs = st.tabs(STORES)
for store_name, tab in zip(STORES, tabs):
    with tab:
        df = st.session_state['df']
        items = df[df['store'] == store_name]
        
        if items.empty:
            st.info("List is empty")
        else:
            sorted_group = items.sort_values("purchased")
            for cat, group in sorted_group.groupby("category", sort=False):
                st.markdown(f"--- \n **{cat}**")
                for _, row in group.iterrows():
                    sid = row['sid']
                    emoji = "✅" if row['purchased'] else "🛒"
                    style = "text-decoration: line-through; color: gray;" if row['purchased'] else ""
                    
                    # Row Layout: Toggle (Left), Text (Center), Delete (Right)
                    # The CSS at the top ensures these stay locked in a row
                    cols = st.columns([1, 6, 1])
                    
                    if cols[0].button(emoji, key=f"t_{sid}"):
                        idx = df.index[df['sid'] == sid].tolist()[0]
                        st.session_state['df'].at[idx, "purchased"] = not row["purchased"]
                        st.session_state['needs_save'] = True
                        st.rerun()
                    
                    cols[1].markdown(f"<div class='item-text' style='{style}'>{row['item']}</div>", unsafe_allow_html=True)
                    
                    if cols[2].button("🗑️", key=f"d_{sid}"):
                        st.session_state['df'] = df[df['sid'] != sid].reset_index(drop=True)
                        st.session_state['needs_save'] = True
                        st.rerun()
