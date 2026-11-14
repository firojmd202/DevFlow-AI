"""Phase 0 page notices."""

import streamlit as st


def phase0_placeholder(feature_name: str) -> None:
    st.info(
        f"{feature_name}\n\nThis feature will be available in a future phase.",
        title="Phase 0 — Not yet implemented",
    )
