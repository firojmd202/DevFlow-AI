"""Backend health and integration configuration summary."""

import asyncio

import streamlit as st
from pydantic import ValidationError

from devflow_core.config import get_settings
from devflow_core.mcp_config import MCPServerConfig
from devflow_ui.api_client import APIClient


def render_settings() -> None:
    st.header("Settings")
    try:
        settings = get_settings()
    except ValidationError:
        st.error("Application settings are invalid. Check the local configuration.")
        return
    client = APIClient(settings.DEVFLOW_API_BASE_URL)
    with st.spinner("Loading integration settings…"):
        integrations = asyncio.run(client.list_integrations())
    if integrations is None:
        st.warning("Integration settings are unavailable.")
    else:
        live = sum(row.get("mode") == "live" for row in integrations)
        st.text(f"Integrations: {live} live · {len(integrations) - live} stub")
    st.text(f"MCP servers configured: {len(MCPServerConfig.from_settings(settings))}")
    if integrations is not None:
        github_live = any(
            row.get("name") == "github" and row.get("mode") == "live" for row in integrations
        )
        if github_live:
            github_health = asyncio.run(client.get_integration_health("github"))
            if github_health is not None and github_health.get("status") == "ok":
                st.text("GitHub: connected")
            else:
                st.text("GitHub: unavailable")
        else:
            st.text("GitHub: no token configured")

    if st.button("Check backend health"):
        health = asyncio.run(client.get_health())
        if health is None:
            st.warning("API unavailable — start the backend to connect.")
        else:
            st.text(f"Backend: {health['status']} · version {health['version']}")


render_settings()
