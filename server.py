from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_infostat.config import AppConfig, load_config
from mcp_infostat.errors import InfoStatError, build_error_payload
from mcp_infostat.results.capture import InfoStatResultsCapture
from mcp_infostat.security import PathSecurityPolicy
from mcp_infostat.session import InfoStatSessionManager
from mcp_infostat.utils import build_response


CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"
CONFIG: AppConfig = load_config(CONFIG_PATH)
SECURITY_POLICY = PathSecurityPolicy(
    base_dir=CONFIG.paths.data_base_dir,
    allowed_extensions=tuple(CONFIG.security.allowed_extensions),
    max_file_size_mb=CONFIG.security.max_file_size_mb,
)
SESSION = InfoStatSessionManager(config=CONFIG)
RESULTS_CAPTURE = InfoStatResultsCapture(session=SESSION)

mcp = FastMCP("MCP-InfoStat")


def _run_tool(operation: str, fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    started = time.perf_counter()
    warnings: list[str] = []
    try:
        result = fn(*args, **kwargs)
        return build_response(
            success=True,
            operation=operation,
            started_at=started,
            result=result,
            warnings=warnings,
        )
    except InfoStatError as exc:
        return build_response(
            success=False,
            operation=operation,
            started_at=started,
            result={},
            warnings=warnings,
            error=build_error_payload(exc),
        )
    except Exception as exc:  # pragma: no cover - fallback de seguridad
        wrapped = InfoStatError(
            code="UNEXPECTED_ERROR",
            message="Error no esperado durante la ejecucion de la tool.",
            details={"exception_type": type(exc).__name__, "raw": str(exc)},
        )
        return build_response(
            success=False,
            operation=operation,
            started_at=started,
            result={},
            warnings=warnings,
            error=build_error_payload(wrapped),
        )


@mcp.tool()
def infostat_launch(infostat_path: str | None = None, timeout_seconds: float = 30) -> dict[str, Any]:
    """Lanza InfoStat 2008 y establece una sesion activa."""

    def _impl() -> dict[str, Any]:
        return SESSION.launch(exe_path=infostat_path, timeout=timeout_seconds)

    return _run_tool("infostat_launch", _impl)


@mcp.tool()
def infostat_status() -> dict[str, Any]:
    """Retorna el estado actual de la sesion InfoStat."""
    return _run_tool("infostat_status", SESSION.status)


@mcp.tool()
def infostat_close(save_before_close: bool = False) -> dict[str, Any]:
    """Cierra InfoStat de forma limpia."""

    def _impl() -> dict[str, Any]:
        return SESSION.close(save_before_close=save_before_close)

    return _run_tool("infostat_close", _impl)


@mcp.tool()
def data_load(
    file_path: str,
    sheet_name: str | None = None,
    delimiter: str | None = None,
    has_header: bool = True,
) -> dict[str, Any]:
    """Valida y carga un dataset para la sesion activa de InfoStat."""

    def _impl() -> dict[str, Any]:
        safe_path = SECURITY_POLICY.validate_input_path(file_path)
        return SESSION.data_load(
            file_path=safe_path,
            sheet_name=sheet_name,
            delimiter=delimiter,
            has_header=has_header,
        )

    return _run_tool("data_load", _impl)


@mcp.tool()
def data_get_info() -> dict[str, Any]:
    """Retorna metadatos del dataset activo."""
    return _run_tool("data_get_info", SESSION.data_get_info)


@mcp.tool()
def results_get_last(format: str = "raw_text", analysis_type: str | None = None) -> dict[str, Any]:
    """Retorna resultados de InfoStat en formato raw_text o structured."""

    def _impl() -> dict[str, Any]:
        return RESULTS_CAPTURE.get_last(format=format, analysis_type=analysis_type)

    return _run_tool("results_get_last", _impl)


def main() -> None:
    if CONFIG.mcp.transport != "stdio":
        raise RuntimeError("El hito actual soporta solo transporte stdio.")
    mcp.run()


if __name__ == "__main__":
    main()
