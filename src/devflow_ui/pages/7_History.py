"""Execution history and audit counts from the backend."""

import asyncio
from datetime import datetime

import streamlit as st

from devflow_core.config import get_settings
from devflow_ui.api_client import APIClient


def render_history() -> None:
    st.header("History")
    client = APIClient(get_settings().DEVFLOW_API_BASE_URL)
    with st.spinner("Loading execution history…"):
        workflows = asyncio.run(client.list_workflows())
        if workflows is None:
            st.warning("Execution history is unavailable.")
            return
        rows: list[tuple[datetime, int, dict[str, object]]] = []
        incomplete = False
        for workflow in workflows:
            runs = asyncio.run(client.list_runs(int(str(workflow["id"]))))
            if runs is None:
                incomplete = True
                continue
            for run in runs:
                run_id = int(str(run["id"]))
                audit = asyncio.run(client.list_run_audit(run_id))
                incomplete |= audit is None
                rows.append(
                    (
                        datetime.fromisoformat(str(run.get("started_at") or run["created_at"])),
                        run_id,
                        {
                            "Workflow": workflow["name"],
                            "Run status": run["status"],
                            "Started at": run.get("started_at") or "—",
                            "Completed at": run.get("completed_at") or "—",
                            "Event count": len(audit) if audit is not None else None,
                        },
                    )
                )

    if incomplete:
        st.warning("Some execution history is unavailable.")
    if rows:
        rows.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
        st.dataframe([row for _, _, row in rows], hide_index=True)
    elif not incomplete:
        st.info("No workflow runs yet.")


render_history()
