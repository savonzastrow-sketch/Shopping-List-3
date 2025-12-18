import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

# Wide layout is required to use the full screen width
st.set_page_config(page_title="🛒 Shopping List", layout="wide")

# --- THE NEW "NO-COLUMNS" CSS ---
st.markdown("""
<style>
    .block-container {
        padding: 1rem 0.5rem !important;
        max-width: 100% !important;
    }

    /* A clean, single-container row that doesn't use Streamlit columns */
    .custom-row {
        display: flex;
        align-items: center;
        width: 100%;
        padding: 8px 0;
        border-bottom: 1px solid #f0f2f6; /* Optional: adds a thin line between items */
    }

    .row-item-text {
        flex-grow: 1;
        font-size: 18px;
        padding: 0 10px;
        text-align: left;
    }

    /* Make buttons tiny and borderless */
    div.stButton > button {
        border: none !important;
        background: transparent !important;
        padding: 0 !important;
        font-size: 24px !important;
        width: 40px !important;
        height: 40px !important;
    }

    @media (min-width: 800px) {
        .block-container { max-width: 500px !important; margin: auto !important; }
    }
</style>
""", unsafe_allow_html=True)

# ... (Previous Setup/Data code remains the same) ...

# 5. TABS & LIST (The Row Rewrite)
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
                st.markdown(f"### {cat}")
                
                for _, row in group.iterrows():
                    sid = row['sid']
                    emoji = "✅" if row['purchased'] else "🛒"
                    style = "text-decoration: line-through; color: gray;" if row['purchased'] else ""
                    
                    # WE USE ONE HORIZONTAL BLOCK INSTEAD OF 3 COLUMNS
                    # Wrapping this in a custom div to ensure it stays pinned left
                    st.markdown(f"<div class='custom-row'>", unsafe_allow_html=True)
                    
                    # We use standard columns here but with a very tiny ratio 
                    # to keep them tightly grouped
                    c_btn, c_txt, c_del = st.columns([0.15, 0.7, 0.15])
                    
                    with c_btn:
                        if st.button(emoji, key=f"t_{sid}"):
                            idx = df.index[df['sid'] == sid].tolist()[0]
                            st.session_state['df'].at[idx, "purchased"] = not row["purchased"]
                            st.session_state['needs_save'] = True
                            st.rerun()
                    
                    with c_txt:
                        st.markdown(f"<div class='row-item-text' style='{style}'>{row['item']}</div>", unsafe_allow_html=True)
                    
                    with c_del:
                        if st.button("🗑️", key=f"d_{sid}"):
                            st.session_state['df'] = df[df['sid'] != sid].reset_index(drop=True)
                            st.session_state['needs_save'] = True
                            st.rerun()
                            
                    st.markdown("</div>", unsafe_allow_html=True)

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
if 'df' not in st.session_state or st.session_state['df'] is None:
    st.session_state['df'] = load_data()
    
if 'needs_save' not in st.session_state:
    st.session_state['needs_save'] = False

# This line is the 'Safety Net' - it creates a local variable for the UI to use
df = st.session_state['df']

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
                    
                    # Using a tiny ratio (0.15) for the buttons keeps them anchored left
                    c_btn, c_txt, c_del = st.columns([0.15, 0.7, 0.15])
                    
                    with c_btn:
                        # 'key' must be unique for every button in Streamlit
                        if st.button(emoji, key=f"t_{sid}"):
                            idx = df.index[df['sid'] == sid].tolist()[0]
                            st.session_state['df'].at[idx, "purchased"] = not row["purchased"]
                            st.session_state['needs_save'] = True
                            st.rerun()
                    
                    with c_txt:
                        # This div class 'item-text' maps to the CSS we wrote earlier
                        st.markdown(f"<div class='item-text' style='{style}'>{row['item']}</div>", unsafe_allow_html=True)
                    
                    with c_del:
                        if st.button("🗑️", key=f"d_{sid}"):
                            st.session_state['df'] = df[df['sid'] != sid].reset_index(drop=True)
                            st.session_state['needs_save'] = True
                            st.rerun()
