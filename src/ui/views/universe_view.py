import streamlit as st
from src.data.universe import UniverseManager, Universe

def render_universe_view():
    st.header("Universe Management")
    
    manager = UniverseManager()
    universes = manager.list_universes()
    
    # Sidebar for selection
    selected_universe_name = st.selectbox("Select Universe", ["Create New"] + universes)
    
    if selected_universe_name == "Create New":
        st.subheader("Create New Universe")
        new_name = st.text_input("Universe Name")
        new_description = st.text_area("Description")
        new_tickers = st.text_area("Tickers (comma separated)", "AAPL, MSFT, GOOGL")
        
        if st.button("Create"):
            if new_name:
                tickers_list = [t.strip().upper() for t in new_tickers.split(",") if t.strip()]
                u = Universe(new_name, tickers_list, new_description)
                manager.save_universe(u)
                st.success(f"Universe {new_name} created!")
                st.rerun()
            else:
                st.error("Name is required")
                
    else:
        u = manager.load_universe(selected_universe_name)
        if u:
            st.subheader(f"Universe: {u.name}")
            st.write(f"**Description:** {u.description}")
            st.write(f"**Tickers ({len(u.tickers)}):**")
            st.write(", ".join(u.tickers))
            
            with st.expander("Edit Universe"):
                edit_description = st.text_area("Description", u.description)
                edit_tickers = st.text_area("Tickers", ", ".join(u.tickers))
                
                if st.button("Update"):
                    tickers_list = [t.strip().upper() for t in edit_tickers.split(",") if t.strip()]
                    u.description = edit_description
                    u.tickers = tickers_list
                    manager.save_universe(u)
                    st.success("Universe updated!")
                    st.rerun()
