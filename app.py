# -----------------------
# CORE LOGIC: HANDLERS
# -----------------------
query_params = st.query_params
df_state = st.session_state.get('df')

if df_state is not None and not df_state.empty:
    # TOGGLE HANDLER
    if "toggle" in query_params:
        # Get the ID and clean it
        t_id = str(query_params["toggle"]).replace("%20", " ").strip()
        
        # LOOSE MATCH: Convert everything to strings and compare
        # This works even if one is a 'Date' and one is 'Text'
        mask = df_state['timestamp'].astype(str).str.contains(t_id, na=False, regex=False)
        
        if mask.any():
            idx = df_state.index[mask].tolist()[0]
            df_state.at[idx, "purchased"] = not df_state.at[idx, "purchased"]
            st.session_state['needs_save'] = True
        
        st.query_params.clear()
        st.rerun()

    # DELETE HANDLER
    if "delete" in query_params:
        t_id = str(query_params["delete"]).replace("%20", " ").strip()
        
        # LOOSE MATCH: Only keep rows that DON'T contain this timestamp
        mask = df_state['timestamp'].astype(str).str.contains(t_id, na=False, regex=False)
        
        if mask.any():
            st.session_state['df'] = df_state[~mask].reset_index(drop=True)
            st.session_state['needs_save'] = True
            
        st.query_params.clear()
        st.rerun()
