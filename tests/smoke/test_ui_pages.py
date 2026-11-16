import ast
from unittest.mock import AsyncMock

import pytest
from streamlit.testing.v1 import AppTest

from devflow_ui.api_client import APIClient
from tests.conftest import ROOT

UI = ROOT / "src/devflow_ui"
PAGES = (
    ("Dashboard", "Dashboard overview and recent activity"),
    ("Projects", "Project organization"),
    ("Learning", "Learning plans and progress"),
    ("Specifications", "Specification authoring"),
    ("Design", "Design workflows"),
    ("Workflows", ""),
    ("History", ""),
    ("Documentation", "Documentation and knowledge"),
    ("Integrations", "Integration workflows"),
    ("Settings", "Application settings"),
)


@pytest.mark.parametrize(
    ("index", "heading", "feature"),
    [(index, *page) for index, page in enumerate(PAGES, 1) if index not in {1, 2, 6, 7}],
)
def test_page_renders_without_exception(index: int, heading: str, feature: str) -> None:
    at = AppTest.from_file(UI / "pages" / f"{index}_{heading}.py").run()
    assert not at.exception
    assert [header.value for header in at.header] == [heading]
    assert feature in at.info[0].value
    assert "Phase 0" in at.info[0].proto.title
    assert not at.metric


def test_dashboard_has_no_fabricated_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    for method in ("list_projects", "list_workflows", "list_approvals"):
        monkeypatch.setattr(APIClient, method, AsyncMock(return_value=None))
    at = AppTest.from_file(UI / "pages/1_Dashboard.py").run()
    assert not at.exception
    assert [metric.value for metric in at.metric] == ["—", "—", "—"]
    assert not at.dataframe
    assert not at.get("vega_lite_chart") and not at.get("plotly_chart")


def test_navigation(monkeypatch: pytest.MonkeyPatch) -> None:
    for method in ("list_projects", "list_workflows", "list_approvals"):
        monkeypatch.setattr(APIClient, method, AsyncMock(return_value=[]))
    source = ast.parse((UI / "app.py").read_text(encoding="utf-8"))
    calls = [
        node.func.attr
        for node in ast.walk(source)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "st"
    ]
    assert calls.count("navigation") == 1 and calls.count("Page") == 10
    at = AppTest.from_file(UI / "app.py").run()
    assert not at.exception and at.header[0].value == "Dashboard"
    for index, (heading, _) in enumerate(PAGES, 1):
        at.switch_page(f"pages/{index}_{heading}.py").run()
        assert not at.exception and at.header[0].value == heading


@pytest.mark.parametrize("health", [None, {"status": "ok", "version": "0.1.0"}])
def test_settings_health(monkeypatch: pytest.MonkeyPatch, health: dict[str, str] | None) -> None:
    get_health = AsyncMock(return_value=health)
    monkeypatch.setattr(APIClient, "get_health", get_health)
    at = AppTest.from_file(UI / "pages/10_Settings.py").run()
    at.button[0].click().run()
    assert not at.exception
    get_health.assert_awaited_once()
    if health is None:
        assert at.warning[0].value == "API unavailable — start the backend to connect."
    else:
        assert at.text[0].value == "Backend: ok · version 0.1.0"


@pytest.mark.parametrize("available", [True, False])
def test_projects_page_renders(monkeypatch: pytest.MonkeyPatch, available: bool) -> None:
    projects = [{"id": 1, "name": "Example project", "status": "active"}] if available else None
    monkeypatch.setattr(APIClient, "list_projects", AsyncMock(return_value=projects))
    create = AsyncMock(return_value=None)
    monkeypatch.setattr(APIClient, "create_project", create)
    at = AppTest.from_file(UI / "pages/2_Projects.py").run()
    assert not at.exception and at.header[0].value == "Projects"
    if not available:
        assert at.warning[0].value.startswith("Backend unavailable")
        return
    assert at.dataframe
    at.button[0].click().run()
    assert not at.exception and at.warning[0].value == "Enter a project name."
    create.assert_not_awaited()
    at.text_input[0].set_value("New project")
    at.button[0].click().run()
    assert not at.exception and at.error[0].value == "Could not create the project."
    create.assert_awaited_once_with("New project", None)


def test_project_edit_and_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    projects = [{"id": 1, "name": "Example project", "status": "active"}]
    listing = AsyncMock(return_value=projects)
    update = AsyncMock(return_value=None)
    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(APIClient, "list_projects", listing)
    monkeypatch.setattr(APIClient, "update_project", update)
    monkeypatch.setattr(APIClient, "delete_project", delete)
    at = AppTest.from_file(UI / "pages/2_Projects.py").run()
    at.text_input[1].set_value("Changed")
    at.button[1].click().run()
    assert not at.exception and at.error[0].value == "Could not update the project."
    update.assert_awaited_once_with(1, name="Changed", description="", status="active")
    assert at.button[2].disabled
    at.checkbox[0].check().run()
    assert not at.button[2].disabled
    listing.side_effect = [projects, []]
    at.button[2].click().run()
    assert not at.exception
    delete.assert_awaited_once_with(1)
