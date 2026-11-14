import json
import logging
from datetime import datetime, timedelta

import pytest
from pydantic import SecretStr
from structlog.contextvars import bound_contextvars

from devflow_core.logging import configure_logging, get_logger


def test_production_json_is_filtered_and_redacted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], synthetic_secret: str
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("CODEX_API_KEY", synthetic_secret)
    configure_logging()
    logger = get_logger("test.logger")
    with bound_contextvars(request_id="synthetic-request"):
        logger.debug("filtered")
        logger.info(
            "event",
            api_key=synthetic_secret,
            nested=[{"authorization": synthetic_secret}, SecretStr(synthetic_secret)],
            detail=f"value {synthetic_secret}",
        )
    output = capsys.readouterr().out
    assert synthetic_secret not in output
    event = json.loads(output)
    assert event["logger"] == "test.logger"
    assert event["level"] == "info" and event["message"] == "event"
    assert event["request_id"] == "synthetic-request"
    assert datetime.fromisoformat(event["timestamp"]).utcoffset() == timedelta(0)
    assert event["api_key"] == "[REDACTED]"
    assert event["nested"] == [{"authorization": "[REDACTED]"}, "[REDACTED]"]
    assert event["detail"] == "value [REDACTED]"


def test_console_override_and_idempotence(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("ERROR", "json")
    handlers = list(logging.getLogger().handlers)
    configure_logging("CRITICAL", "json")
    get_logger("test.logger").debug("readable event")
    assert logging.getLogger().handlers == handlers
    output = capsys.readouterr().out
    assert output.count("readable event") == 1 and "debug" in output
    with pytest.raises(json.JSONDecodeError):
        json.loads(output)
