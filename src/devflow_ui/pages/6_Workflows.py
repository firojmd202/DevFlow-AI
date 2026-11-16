"""Workflow and approval status backed by the API."""

import asyncio

import streamlit as st

from devflow_core.config import get_settings
from devflow_ui.api_client import APIClient


def render_workflows() -> None:
    st.header("Workflows")
    client = APIClient(get_settings().DEVFLOW_API_BASE_URL)
    with st.spinner("Loading workflows…"):
        workflows = asyncio.run(client.list_workflows())
    if workflows is None:
        st.warning("Workflows are unavailable.")
        return
    if not workflows:
        st.info("No workflows yet.")
        return

    for workflow in workflows:
        st.subheader(str(workflow["name"]))
        st.write(f"Workflow status: {workflow['status']}")
        with st.spinner("Loading runs…"):
            runs = asyncio.run(client.list_runs(int(str(workflow["id"]))))
        if runs is None:
            st.warning("Runs are unavailable for this workflow.")
            continue
        if not runs:
            st.info("No runs yet.")
        pending_count = sum(
            len(approvals)
            for run in runs
            if isinstance(approvals := run.get("pending_approvals"), list)
        )
        st.write(f"Pending approvals: {pending_count}")
        for run in reversed(runs):
            st.write(f"Run {run['id']}: {run['status']}")
            approvals = run.get("pending_approvals")
            if run["status"] != "waiting_approval" or not isinstance(approvals, list):
                continue
            for approval in approvals:
                if approval["status"] != "pending":
                    continue
                st.write(str(approval["action_description"]))
                approval_id = int(str(approval["id"]))
                approve, reject = st.columns(2)
                decision = None
                if approve.button("Approve", key=f"approve_{approval_id}"):
                    decision = "approved"
                if reject.button("Reject", key=f"reject_{approval_id}"):
                    decision = "rejected"
                if decision is not None:
                    if asyncio.run(client.resolve_approval(approval_id, decision)) is None:
                        st.error("Could not resolve the approval.")
                    else:
                        st.rerun()


render_workflows()
