# ADR-0004: Streamlit UI

## Status: Accepted

## Context

Phase 0 needs a Python UI for the application workflow.

## Decision

Use Streamlit with one st.navigation tree and an HTTP client for backend access.

## Consequences

UI smoke tests exercise page rendering independently. The API owns domain state.
