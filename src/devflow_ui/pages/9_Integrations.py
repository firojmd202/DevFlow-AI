"""Live and stub integration status."""

import asyncio

import streamlit as st

from devflow_core.config import get_settings
from devflow_ui.api_client import APIClient

st.header("Integrations")
client = APIClient(get_settings().DEVFLOW_API_BASE_URL)
with st.spinner("Loading integrations…"):
    integrations = asyncio.run(client.list_integrations())

if integrations is None:
    st.warning("Integration status is unavailable.")
elif not integrations:
    st.info("No integrations are configured.")
else:
    for integration in integrations:
        name = str(integration["name"])
        with st.expander(name):
            st.write(f"Mode: {integration['mode']}")
            st.write(f"Execution mode: {integration['execution_mode']}")
            if st.button("Check status", key=f"health_{name}"):
                health = asyncio.run(client.get_integration_health(name))
                if health is None:
                    st.warning("Could not check integration status.")
                else:
                    st.write(f"Status: {health['status']}")
