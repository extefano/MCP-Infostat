import pytest

from mcp_infostat.errors import InfoStatError
from mcp_infostat.results.capture import InfoStatResultsCapture


class DummySession:
    def __init__(self, raw_text: str, is_ready: bool = True) -> None:
        self._raw_text = raw_text
        self._is_ready = is_ready

    def _ensure_ready(self) -> None:
        if not self._is_ready:
            raise InfoStatError(code="SESSION_NOT_ACTIVE", message="Sesion no activa")

    def get_last_result(self) -> str:
        return self._raw_text


def test_get_last_returns_raw_text() -> None:
    capture = InfoStatResultsCapture(session=DummySession(raw_text="resultado"))

    result = capture.get_last(format="raw_text")

    assert result == {
        "format": "raw_text",
        "operation_name": "results_get_last",
        "raw_text": "resultado",
    }


def test_get_last_structured_requires_analysis_type() -> None:
    capture = InfoStatResultsCapture(session=DummySession(raw_text="algo"))

    with pytest.raises(InfoStatError) as exc_info:
        capture.get_last(format="structured", analysis_type=None)

    assert exc_info.value.code == "MISSING_ANALYSIS_TYPE"


def test_get_last_structured_rejects_empty_result_buffer() -> None:
    capture = InfoStatResultsCapture(session=DummySession(raw_text="   "))

    with pytest.raises(InfoStatError) as exc_info:
        capture.get_last(format="structured", analysis_type="descriptivos")

    assert exc_info.value.code == "RESULTS_EMPTY"


def test_get_last_structured_parses_payload() -> None:
    raw_text = """
Estadisticas descriptivas
Variable: Altura
N: 30
Media: 172.30
"""
    capture = InfoStatResultsCapture(session=DummySession(raw_text=raw_text))

    result = capture.get_last(format="structured", analysis_type="descriptivos")

    assert result["format"] == "structured"
    assert result["analysis_type"] == "descriptivos"
    assert result["structured"] == {
        "tipo": "descriptivos",
        "variables": [{"nombre": "Altura", "n": 30, "media": 172.3}],
    }


def test_get_last_structured_reports_parse_failure() -> None:
    capture = InfoStatResultsCapture(session=DummySession(raw_text="texto sin patron"))

    with pytest.raises(InfoStatError) as exc_info:
        capture.get_last(format="structured", analysis_type="anova_dca")

    assert exc_info.value.code == "RESULTS_PARSE_FAILED"
