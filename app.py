import streamlit as st
import pandas as pd
import gspread

# 1. SETUP & CONFIG
SHEET_NAME = "Shopping_List_Data"
CATEGORIES = ["Vegetables", "Beverages", "Meat/Dairy", "Frozen", "Dry Goods"]
STORES = ["Costco", "Trader Joe's", "Whole Foods", "Other"]

# 'Wide' layout is essential to reclaim the side margins on mobile
st.set_page_config(page_title="🛒 Shopping List", layout="wide")

# --- THE "SAFE" MOBILE CSS ---
st.markdown("""
<style>
    /* 1. Reclaim side spaces on phones */
    .block-container {
        padding: 1rem 0.5rem !important;
        max-width: 100% !important;
    }

    /* 2. Desktop Constraint (keeps it centered on big screens) */
    @media (min-width: 800px) {
        .block-container { max-width: 550px !important; margin: auto !important; }
    }

    /* 3. ONLY target the shopping list rows for the 'No-Wrap' fix */
    /* This prevents your Save/Refresh buttons from breaking */
    .list-row [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 0px !important;
    }

    /* 4. Style the row-level emojis to be big and clickable */
    .list-row button {
        border: none !important;
        background: transparent !important;
        font-size: 22px !important;
        padding: 0px !important;
    }

    /* 5. Ensure item text doesn't collapse */
    .item-text {
        font-size: 18px;
        padding-left: 10px;
        white-space: normal; /* Allow text to wrap internally if very long */
    }
</style>
""", unsafe_allow_html=True)

# 2. DATA FUNCTIONS (Updated for better Refreshing)
@st.cache_data(ttl=600) # Auto-refresh every 10 mins or manually
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
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame(columns=["sid", "item", "purchased", "category", "store"])

# 3. INITIALIZE STATE
if 'df' not in st.session_state:
    st.session_state['df'] = load_data()
    st.session_state['needs_save'] = False

# 4. APP HEADER
st.markdown("<h1 style='text-align: center;'>🛒 Shopping List</h1>", unsafe_allow_html=True)

# Main Controls (Using standard columns so they look like buttons again)
c1, c2 = st.columns(2)
if c1.button("☁️ Save Cloud", use_container_width=True, type="primary"):
    try:
        client = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        sh = client.open(SHEET_NAME).sheet1
        clean_df = st.session_state['df'].drop(columns=['sid']).astype(str)
        sh.clear()
        sh.append_rows([clean_df.columns.values.tolist()] + clean_df.values.tolist(), value_input_option='USER_ENTERED')
        st.session_state['needs_save'] = False
        st.toast("Saved to Google Sheets! ✅")
    except Exception as e:
        st.error(f"Save failed: {e}")

if c2.button("🔄 Refresh", use_container_width=True):
    st.cache_data.clear() # CRITICAL: This wipes the cache to get fresh sheet data
    st.session_state['df'] = load_data()
    st.rerun()

# Expandable Add Form
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
        # Filter items and strip whitespace to prevent "invisible" items
        items = df[df['store'].str.strip() == store_name.strip()]
        
        if items.empty:
            st.info("No items for this store.")
        else:
            # Group by Category
            sorted_items = items.sort_values("purchased")
            for cat, group in sorted_items.groupby("category", sort=False):
                st.markdown(f"#### {cat}")
                
                # Wrap the list in a custom div to apply the "No-Wrap" CSS
                st.markdown("<div class='list-row'>", unsafe_allow_html=True)
                for _, row in group.iterrows():
                    sid = row['sid']
                    emoji = "✅" if row['purchased'] else "🛒"
                    style = "text-decoration: line-through; color: gray;" if row['purchased'] else ""
                    
                    # Columns for the row: Icon, Text, Trash
                    cols = st.columns([1, 7, 1])
                    
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
                st.markdown("</div>", unsafe_allow_html=True)
