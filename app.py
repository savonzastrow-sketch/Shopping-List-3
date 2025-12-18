import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

# Wide layout is required to use the full screen width
st.set_page_config(page_title="🛒 Shopping List", layout="wide")

# --- THE "STRICT NO-WRAP" CSS ---
st.markdown("""
<style>
    /* 1. Eliminate the side 'blank spaces' (gutters) */
    .block-container {
        padding: 1rem 0.5rem !important;
        max-width: 100% !important;
    }

    /* 2. FORCE columns to stay in a row & PIN content to the left */
    [data-testid="column"] {
        width: unset !important;
        flex: unset !important;
        min-width: 0px !important;
        display: flex !important;
        justify-content: flex-start !important; /* Forces content to the left */
        align-items: center !important;
    }

    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        justify-content: flex-start !important; /* Prevents center-justification */
        gap: 0px !important; /* Removes the gap between button and text */
    }

    /* 3. Precise width control */
    [data-testid="column"]:nth-of-type(1) {
        width: 40px !important; /* Fixed narrow width for checkbox */
    }
    [data-testid="column"]:nth-of-type(2) {
        flex-grow: 1 !important; /* Text takes all remaining space */
        padding-left: 5px !important; /* Tight spacing between icon and text */
    }
    [data-testid="column"]:nth-of-type(3) {
        width: 40px !important; /* Fixed narrow width for trash */
    }

    /* 4. Remove automatic centering margins from the text itself */
    [data-testid="stMarkdownContainer"] p {
        margin: 0 !important;
        text-align: left !important;
    }

    /* 5. Button styling (Invisible but clickable) */
    div[data-testid="column"] button {
        border: none !important;
        background: transparent !important;
        font-size: 24px !important;
        padding: 0 !important;
        height: 40px !important;
        width: 40px !important;
        margin: 0 !important;
    }

    .item-text {
        font-size: 18px;
        line-height: 1.1;
        text-align: left !important;
    }

    /* Desktop constraint */
    @media (min-width: 800px) {
        .block-container { max-width: 500px !important; margin: auto !important; }
    }
</style>
""", unsafe_allow_html=True)

# 2. DATA FUNCTIONS (Cleaned for better refresh)
@st.cache_data(ttl=600)
def load_data():
    try:
        client = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        sh = client.open(SHEET_NAME).sheet1
        df = pd.DataFrame(sh.get_all_records())
        if df.empty:
            df = pd.DataFrame(columns=["sid", "item", "purchased", "category", "store"])
        if 'sid' not in df.columns:
            df = df.reset_index().rename(columns={'index': 'sid'})
        df["purchased"] = df["purchased"].astype(str).str.lower().map({'true': True, 'false': False}).fillna(False)
        return df
    except:
        return pd.DataFrame(columns=["sid", "item", "purchased", "category", "store"])

# 3. INITIALIZE STATE
if 'df' not in st.session_state:
    st.session_state['df'] = load_data()
    st.session_state['needs_save'] = False

# 4. APP UI
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>🛒 Shopping List</h1>", unsafe_allow_html=True)

# Action Buttons
c_s, c_r = st.columns(2)
if c_s.button("☁️ Save Cloud", use_container_width=True, type="primary"):
    try:
        client = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        sh = client.open(SHEET_NAME).sheet1
        clean_df = st.session_state['df'].drop(columns=['sid']).astype(str)
        sh.clear()
        sh.append_rows([clean_df.columns.values.tolist()] + clean_df.values.tolist(), value_input_option='USER_ENTERED')
        st.session_state['needs_save'] = False
        st.toast("Saved! ✅")
    except Exception as e:
        st.error(f"Error: {e}")

if c_r.button("🔄 Refresh", use_container_width=True):
    st.cache_data.clear() # Forces a re-fetch from Google
    st.session_state['df'] = load_data()
    st.rerun()

# 5. LIST VIEW
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
                    
                    # This row will NOT wrap because of the min-width: 0 CSS
                    cols = st.columns([1, 8, 1])
                    
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
