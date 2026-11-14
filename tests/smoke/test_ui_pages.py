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
    ("Coding", "Coding and execution"),
    ("Testing", "Testing and quality checks"),
    ("Documentation", "Documentation and knowledge"),
    ("Integrations", "Integration workflows"),
    ("Settings", "Application settings"),
)


@pytest.mark.parametrize(
    ("index", "heading", "feature"),
    [(index, *page) for index, page in enumerate(PAGES, 1)],
)
def test_page_renders_without_exception(index: int, heading: str, feature: str) -> None:
    at = AppTest.from_file(UI / "pages" / f"{index}_{heading}.py").run()
    assert not at.exception
    assert [header.value for header in at.header] == [heading]
    assert feature in at.info[0].value
    assert "Phase 0" in at.info[0].proto.title
    assert not at.metric


def test_dashboard_has_no_fabricated_metrics() -> None:
    at = AppTest.from_file(UI / "pages/1_Dashboard.py").run()
    assert not at.exception
    assert not at.metric and not at.dataframe
    assert not at.get("vega_lite_chart") and not at.get("plotly_chart")


def test_navigation() -> None:
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
