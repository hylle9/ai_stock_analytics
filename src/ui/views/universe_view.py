import streamlit as st
from src.data.universe import UniverseManager, Universe

def render_universe_view():
    st.header("Universe Management")
    
    manager = UniverseManager()
    universes = manager.list_universes()
    
    # Sidebar for selection using session state for control
    if "universe_action" not in st.session_state:
        st.session_state.universe_action = "Manage Existing"
        
    action = st.sidebar.radio("Action", ["Manage Existing", "Create New"], key="universe_action")

    if action == "Create New":
        st.subheader("Create New Universe")
        
        # Check limit early
        if len(universes) >= 10:
            st.error(f"Universe limit reached ({len(universes)}/10). Please delete an existing universe first.")
        else:
            with st.form("create_universe_form"):
                new_name = st.text_input("Universe Name")
                new_description = st.text_area("Description")
                new_tickers = st.text_area("Tickers (comma separated)", "AAPL, MSFT, GOOGL")
                
                if st.form_submit_button("Create"):
                    if new_name:
                        if new_name in universes:
                            st.error("Universe with this name already exists.")
                        else:
                            tickers_list = [t.strip().upper() for t in new_tickers.split(",") if t.strip()]
                            u = Universe(new_name, tickers_list, new_description)
                            try:
                                manager.save_universe(u)
                                st.success(f"Universe '{new_name}' created!")
                                # Switch to manage view
                                st.session_state.universe_action = "Manage Existing"
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    else:
                        st.error("Name is required")

    elif action == "Manage Existing":
        if not universes:
            st.info("No universes found. Create one to get started.")
            return

        selected_universe_name = st.sidebar.selectbox("Select Universe", universes)
        
        if selected_universe_name:
            u = manager.load_universe(selected_universe_name)
            if u:
                # Header showing details
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(f"🌌 {u.name}")
                    st.caption(u.description)
                with c2:
                    st.metric("Tickers", len(u.tickers))
                
                st.divider()
                
                # Edit Section
                with st.expander("Edit Universe", expanded=True):
                    with st.form("edit_universe_form"):
                        edit_description = st.text_area("Description", u.description)
                        edit_tickers = st.text_area("Tickers (comma separated)", ", ".join(u.tickers), height=150)
                        
                        c_update, c_delete = st.columns([1, 1])
                        
                        submitted = st.form_submit_button("Update Universe")
                        if submitted:
                            tickers_list = [t.strip().upper() for t in edit_tickers.split(",") if t.strip()]
                            u.description = edit_description
                            u.tickers = tickers_list
                            manager.save_universe(u)
                            st.success("Universe updated successfully!")
                            st.rerun()
                
                # Delete Section (Separate from form to avoid conflicts)
                st.markdown("---")
                st.warning("Danger Zone")
                if st.button(f"Delete '{u.name}'", type="primary"):
                    manager.delete_universe(u.name)
                    st.success(f"Deleted '{u.name}'")
                    st.rerun()
                
                # Display Tickers
                st.subheader("Included Assets")
                st.write(", ".join(u.tickers))
