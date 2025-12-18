import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

# 'Wide' is required to unlock the full screen width on mobile
st.set_page_config(page_title="🛒 Shopping List", layout="wide")

# --- THE HTML GRID & PORTRAIT FIX ---
st.markdown("""
<style>
    /* 1. Eliminate the 'Gutters' (Blank side spaces) */
    .block-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-top: 1rem !important;
        max-width: 100% !important;
    }

    /* 2. Force the Row to be a true horizontal grid with no gaps */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 0px !important;
    }

    /* 3. Style columns to act as tight grid cells */
    [data-testid="column"] {
        width: min-content !important;
        flex: unset !important;
        padding: 0px !important;
    }
    
    /* Set specific widths: Icon cells are 45px, Text cell grows to fill */
    [data-testid="column"]:nth-of-type(1), [data-testid="column"]:nth-of-type(3) {
        width: 48px !important;
    }
    [data-testid="column"]:nth-of-type(2) {
        flex-grow: 1 !important;
        width: auto !important;
    }

    /* 4. Make buttons fill the grid cell perfectly */
    div[data-testid="column"] button {
        border: none !important;
        background: transparent !important;
        width: 100% !important;
        height: 50px !important;
        padding: 0px !important;
        margin: 0px !important;
        font-size: 24px !important;
        box-shadow: none !important;
    }

    /* 5. Item Text styling */
    .item-text {
        font-size: 19px;
        padding-left: 8px;
        line-height: 1.2;
    }

    /* 6. Fix for Tablet/Desktop - Keep it centered if the screen is huge */
    @media (min-width: 800px) {
        .block-container {
            max-width: 500px !important;
            margin: auto !important;
        }
    }
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

# 4. APP UI
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>🛒 Shopping List</h1>", unsafe_allow_html=True)

# Control Buttons
c1, c2 = st.columns(2)
if c1.button("☁️ Save Cloud", use_container_width=True):
    try:
        client = get_client()
        sh = client.open(SHEET_NAME).sheet1
        clean_df = st.session_state['df'].drop(columns=['sid']).astype(str)
        sh.clear()
        sh.append_rows([clean_df.columns.values.tolist()] + clean_df.values.tolist(), value_input_option='USER_ENTERED')
        st.session_state['needs_save'] = False
        st.success("Saved!")
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

if c2.button("🔄 Refresh", use_container_width=True):
    st.session_state['df'] = None
    st.rerun()

if st.session_state['needs_save']:
    st.markdown("<p style='text-align:center; color:red; font-size:12px; margin:0;'>⚠️ Unsaved changes</p>", unsafe_allow_html=True)

with st.expander("➕ Add New Item"):
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
            st.info("No items.")
        else:
            sorted_group = items.sort_values("purchased")
            for cat, group in sorted_group.groupby("category", sort=False):
                st.markdown(f"**{cat}**")
                for _, row in group.iterrows():
                    sid = row['sid']
                    emoji = "✅" if row['purchased'] else "🛒"
                    style = "text-decoration: line-through; color: gray;" if row['purchased'] else ""
