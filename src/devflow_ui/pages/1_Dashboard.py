"""Live dashboard metrics from the backend."""

import asyncio

import streamlit as st

from devflow_core.config import get_settings
from devflow_ui.api_client import APIClient


async def count_projects(client: APIClient) -> int | None:
    limit = 50
    total = 0
    while True:
        page = await client.list_projects(limit=limit, offset=total)
        if page is None:
            return None
        total += len(page)
        if len(page) < limit:
            return total


async def load_metrics(client: APIClient) -> tuple[int | None, int | None, int | None]:
    projects, workflows, approvals = await asyncio.gather(
        count_projects(client),
        client.list_workflows(status="active"),
        client.list_approvals(status="pending"),
    )
    return (
        projects,
        len(workflows) if workflows is not None else None,
        (len(approvals) if approvals is not None else None),
    )


st.header("Dashboard")
with st.spinner("Loading dashboard…"):
    metrics = asyncio.run(load_metrics(APIClient(get_settings().DEVFLOW_API_BASE_URL)))
for column, label, value in zip(
    st.columns(3), ("Projects", "Active workflows", "Pending approvals"), metrics, strict=True
):
    column.metric(label, value if value is not None else "—")
if None in metrics:
    st.warning("Some dashboard metrics are unavailable.")
