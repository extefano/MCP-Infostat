from __future__ import annotations

from typing import Any

from mcp_infostat.errors import InfoStatError
from mcp_infostat.results.parser import parse_infostat_output
from mcp_infostat.session import InfoStatSessionManager


class InfoStatResultsCapture:
    def __init__(self, session: InfoStatSessionManager):
        self.session = session

    def get_last(self, format: str = "raw_text", analysis_type: str | None = None) -> dict[str, Any]:
        if format not in {"raw_text", "structured"}:
            raise InfoStatError(
                code="INVALID_RESULTS_FORMAT",
                message="Formato invalido para results_get_last.",
                details={"allowed": ["raw_text", "structured"], "requested": format},
            )

        self.session._ensure_ready()
        raw_text = self.session.get_last_result()

        if format == "structured":
            if analysis_type is None:
                raise InfoStatError(
                    code="MISSING_ANALYSIS_TYPE",
                    message="analysis_type es requerido cuando format='structured'.",
                    details={"allowed": ["descriptivos", "normalidad", "anova_dca"]},
                )

            if not raw_text.strip():
                raise InfoStatError(
                    code="RESULTS_EMPTY",
                    message="No hay resultados disponibles para parsear en modo structured.",
                )

            try:
                structured = parse_infostat_output(raw_text=raw_text, analysis_type=analysis_type)
            except ValueError as exc:
                raise InfoStatError(
                    code="RESULTS_PARSE_FAILED",
                    message="No se pudo parsear la salida de InfoStat en modo structured.",
                    details={"analysis_type": analysis_type, "raw": str(exc)},
                ) from exc

            return {
                "format": "structured",
                "operation_name": "results_get_last",
                "analysis_type": analysis_type,
                "structured": structured,
                "raw_text": raw_text,
            }

        return {
            "format": "raw_text",
            "operation_name": "results_get_last",
            "raw_text": raw_text,
        }
