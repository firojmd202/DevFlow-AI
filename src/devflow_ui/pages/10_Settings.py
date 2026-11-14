"""Settings page."""

import asyncio

import streamlit as st

from devflow_core.config import get_settings
from devflow_ui.api_client import APIClient
from devflow_ui.components.placeholders import phase0_placeholder

st.header("Settings")
phase0_placeholder("Application settings")

if st.button("Check backend health"):
    health = asyncio.run(APIClient(get_settings().DEVFLOW_API_BASE_URL).get_health())
    if health is None:
        st.warning("API unavailable — start the backend to connect.")
    else:
        st.text(f"Backend: {health['status']} · version {health['version']}")
