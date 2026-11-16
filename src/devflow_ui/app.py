"""Streamlit entry point and navigation."""

import streamlit as st

from devflow_ui.components.sidebar import render_sidebar


def main() -> None:
    st.set_page_config(page_title="DevFlow AI", page_icon="🤖", layout="wide")
    pages = [
        st.Page("pages/1_Dashboard.py", title="Dashboard", icon="🏠"),
        st.Page("pages/2_Projects.py", title="Projects", icon="📁"),
        st.Page("pages/3_Learning.py", title="Learning", icon="📚"),
        st.Page("pages/4_Specifications.py", title="Specifications", icon="📋"),
        st.Page("pages/5_Design.py", title="Design", icon="🎨"),
        st.Page("pages/6_Workflows.py", title="Workflows", icon="💻"),
        st.Page("pages/7_History.py", title="History", icon="🧪"),
        st.Page("pages/8_Documentation.py", title="Documentation", icon="📖"),
        st.Page("pages/9_Integrations.py", title="Integrations", icon="🔌"),
        st.Page("pages/10_Settings.py", title="Settings", icon="⚙️"),
    ]
    page = st.navigation(pages)
    render_sidebar()
    page.run()


if __name__ == "__main__":
    main()
