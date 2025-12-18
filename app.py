import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

# SWITCHED TO WIDE: This removes the mandatory side gutters
st.set_page_config(page_title="🛒 Shopping List", layout="wide")

# --- THE PORTRAIT FIX: Edge-to-Edge CSS ---
st.markdown("""
<style>
    /* 1. Desktop vs Mobile logic */
    @media (min-width: 600px) {
        .block-container {
            max-width: 500px !important;
            margin: auto !important;
        }
    }
    
    /* 2. Remove all extra padding for mobile portrait */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 5rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* 3. Force the Row to use every pixel available */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 0px !important; /* Zero gap for tighter fit */
    }

    /* 4. Thumb-ready icons with no border */
    div[data-testid="stColumn"] button {
        border: none !important;
        background: transparent !important;
        padding: 0px !important;
        font-size: 24px !important;
        width: 100% !important;
    }

    .item-text {
        font-size: 19px;
        line-height: 1.2;
        padding-left: 10px;
    }
    
    h1 { text-align: center; font-size: 26px !important; }
    
    /* Shrink the tab font so they fit in portrait */
    button[data-baseweb="tab"] {
        font-size: 14px !important;
        padding-left: 10px !important;
        padding-right: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

# 2. DATA FUNCTIONS (Unchanged for stability)
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
st.markdown("<h1>🛒 Shopping List</h1>", unsafe_allow_html=True)

# Compact Action Buttons
c_save, c_ref = st.columns(2)
if c_save.button("☁️ Save Cloud", use_container_width=True):
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

if c_ref.button("🔄 Refresh", use_container_width=True):
    st.session_state['df'] = None
    st.rerun()

# Expandable Add Form to save vertical space
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
            st.info("No items yet.")
        else:
            sorted_items = items.sort_values("purchased")
            for cat, group in sorted_items.groupby("category", sort=False):
                st.markdown(f"**{cat}**")
                for _, row in group.iterrows():
                    sid = row['sid']
                    emoji = "✅" if row['purchased'] else "🛒"
                    style = "text-decoration: line-through; color: gray;" if row['purchased'] else ""
                    
                    # Row Layout: Minimized side columns to maximize text space
                    cols = st.columns([1.2, 7.6, 1.2])
                    
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
