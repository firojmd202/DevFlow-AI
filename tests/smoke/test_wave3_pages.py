from unittest.mock import AsyncMock

import pytest
from streamlit.testing.v1 import AppTest

from devflow_ui.api_client import APIClient
from tests.conftest import ROOT

PAGES = ROOT / "src/devflow_ui/pages"


def test_dashboard_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    projects = AsyncMock(side_effect=[[{"id": id} for id in range(50)], [{"id": 50}]])
    workflows = AsyncMock(return_value=[{"id": 1}])
    approvals = AsyncMock(return_value=[])
    monkeypatch.setattr(APIClient, "list_projects", projects)
    monkeypatch.setattr(APIClient, "list_workflows", workflows)
    monkeypatch.setattr(APIClient, "list_approvals", approvals)
    at = AppTest.from_file(PAGES / "1_Dashboard.py").run()
    assert not at.exception
    assert [metric.value for metric in at.metric] == ["51", "1", "0"]
    assert projects.await_count == 2
    workflows.assert_awaited_once_with(status="active")
    approvals.assert_awaited_once_with(status="pending")
    assert all("Phase 0" not in item.value for item in at.info)


def test_workflows_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        APIClient,
        "list_workflows",
        AsyncMock(return_value=[{"id": 1, "name": "Review", "status": "active"}]),
    )
    pending = {
        "id": 2,
        "status": "waiting_approval",
        "pending_approvals": [
            {"id": 3, "status": "pending", "action_description": "Review request"}
        ],
    }
    runs = AsyncMock(return_value=[pending])
    monkeypatch.setattr(APIClient, "list_runs", runs)
    resolve = AsyncMock(return_value=None)
    monkeypatch.setattr(APIClient, "resolve_approval", resolve)

    at = AppTest.from_file(PAGES / "6_Workflows.py").run()
    assert not at.exception
    assert [button.label for button in at.button] == ["Approve", "Reject"]
    at.button[0].click().run()
    resolve.assert_awaited_once_with(3, "approved")
    assert at.error[0].value == "Could not resolve the approval."

    resolve.return_value = {"id": 3, "status": "approved"}
    runs.side_effect = [[pending], [{"id": 2, "status": "running", "pending_approvals": []}]]
    at.button[0].click().run()
    assert not at.exception and not at.button and not at.error


def test_history_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        APIClient,
        "list_workflows",
        AsyncMock(return_value=[{"id": 1, "name": "Example"}]),
    )
    monkeypatch.setattr(
        APIClient,
        "list_runs",
        AsyncMock(
            return_value=[
                {"id": 1, "status": "pending", "created_at": "2026-11-01T10:00:00Z"},
                {
                    "id": 2,
                    "status": "completed",
                    "started_at": "2026-11-02T10:00:00Z",
                    "completed_at": "2026-11-02T11:00:00Z",
                },
            ]
        ),
    )
    audit = AsyncMock(side_effect=[[], [{"id": 2}]])
    monkeypatch.setattr(APIClient, "list_run_audit", audit)
    at = AppTest.from_file(PAGES / "7_History.py").run()
    assert not at.exception
    table = at.dataframe[0].value
    assert table["Run status"].tolist() == ["completed", "pending"]
    assert table["Event count"].tolist() == [1, 0]
    assert table["Workflow"].tolist() == ["Example", "Example"]
    assert audit.await_count == 2


@pytest.mark.parametrize("page", ["6_Workflows", "7_History"])
@pytest.mark.parametrize("unavailable", [False, True])
def test_workflow_pages_empty_and_unavailable(
    monkeypatch: pytest.MonkeyPatch, page: str, unavailable: bool
) -> None:
    monkeypatch.setattr(
        APIClient, "list_workflows", AsyncMock(return_value=None if unavailable else [])
    )
    at = AppTest.from_file(PAGES / f"{page}.py").run()
    assert not at.exception
    assert bool(at.warning) is unavailable
    assert bool(at.info) is not unavailable
