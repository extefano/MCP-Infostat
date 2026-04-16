from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_infostat.config import AppConfig
from mcp_infostat.errors import InfoStatError
from mcp_infostat.ui.launcher import InfoStatLauncher


@dataclass
class DatasetInfo:
    path: Path
    rows: int
    columns: list[str]
    has_header: bool
    delimiter: str


@dataclass
class InfoStatSession:
    pid: int | None = None
    ui_backend: str | None = None
    is_ready: bool = False
    active_dataset: Path | None = None
    dataset_info: DatasetInfo | None = None
    results_buffer: list[str] = field(default_factory=list)


class InfoStatSessionManager:
    def __init__(self, config: AppConfig, launcher: InfoStatLauncher | None = None):
        self.config = config
        self.launcher = launcher or InfoStatLauncher(config.infostat.exe_path)
        self.session = InfoStatSession()

    def launch(self, exe_path: str | None = None, timeout: float | None = None) -> dict[str, Any]:
        if self.session.is_ready:
            raise InfoStatError(
                code="SESSION_ALREADY_ACTIVE",
                message="InfoStat ya se encuentra en ejecucion.",
                details={"pid": self.session.pid},
            )

        app_info = self.launcher.launch(
            exe_path=exe_path,
            timeout=timeout or self.config.timeouts.launch_seconds,
        )
        self.session.pid = app_info["pid"]
        self.session.ui_backend = app_info.get("backend")
        self.session.is_ready = True
        return {
            "running": True,
            "pid": self.session.pid,
            "ui_backend": self.session.ui_backend,
            "version": self.config.infostat.version,
            "dataset_loaded": False,
        }

    def status(self) -> dict[str, Any]:
        running = self.session.is_ready and self.launcher.is_ready()
        self.session.is_ready = running
        return {
            "running": running,
            "dataset_loaded": self.session.active_dataset is not None,
            "dataset_name": self.session.active_dataset.name if self.session.active_dataset else None,
            "ready": running,
            "ui_backend": self.session.ui_backend,
            "version": self.config.infostat.version,
        }

    def close(self, save_before_close: bool = False) -> dict[str, Any]:
        if not self.session.is_ready:
            raise InfoStatError(
                code="SESSION_NOT_ACTIVE",
                message="No hay una sesion activa para cerrar.",
            )

        self.launcher.close(save_before_close=save_before_close)
        had_unsaved_changes = False

        self.session = InfoStatSession()
        return {
            "running": False,
            "unsaved_changes": had_unsaved_changes,
        }

    def data_load(
        self,
        file_path: Path,
        sheet_name: str | None,
        delimiter: str | None,
        has_header: bool,
    ) -> dict[str, Any]:
        self._ensure_ready()

        if file_path.suffix.lower() not in {".csv", ".txt"}:
            raise InfoStatError(
                code="DATA_FORMAT_NOT_IMPLEMENTED",
                message="En este hito solo se soporta carga local de CSV/TXT para metadata.",
                details={"requested_extension": file_path.suffix.lower()},
            )

        separator = delimiter or self._detect_delimiter(file_path)
        rows, columns = self._scan_csv(file_path, delimiter=separator, has_header=has_header)

        self.session.active_dataset = file_path
        self.session.dataset_info = DatasetInfo(
            path=file_path,
            rows=rows,
            columns=columns,
            has_header=has_header,
            delimiter=separator,
        )

        try:
            ui_loaded = bool(self.launcher.load_file_via_keyboard(file_path=file_path))
        except InfoStatError:
            raise
        except Exception as exc:
            raise InfoStatError(
                code="DATA_LOAD_UI_FAILED",
                message="Error no esperado al cargar el archivo en la UI de InfoStat.",
                details={
                    "file_path": str(file_path),
                    "exception_type": type(exc).__name__,
                    "raw": str(exc),
                },
            ) from exc

        if not ui_loaded:
            raise InfoStatError(
                code="DATA_LOAD_UI_FAILED",
                message="No se pudo cargar el archivo en InfoStat mediante estrategia de teclado.",
                details={"file_path": str(file_path)},
            )

        return {
            "file_path": str(file_path),
            "rows": rows,
            "cols": len(columns),
            "columns": columns,
            "sheet_name": sheet_name,
            "delimiter": separator,
            "has_header": has_header,
            "mode": "ui_keyboard",
            "ui_loaded": True,
            "ui_backend": self.session.ui_backend,
        }

    def data_get_info(self) -> dict[str, Any]:
        self._ensure_ready()
        info = self.session.dataset_info
        if info is None:
            raise InfoStatError(
                code="DATASET_NOT_LOADED",
                message="No hay un dataset cargado en la sesion.",
            )

        return {
            "file_path": str(info.path),
            "n_rows": info.rows,
            "n_cols": len(info.columns),
            "columns": info.columns,
            "delimiter": info.delimiter,
            "has_header": info.has_header,
        }

    def append_result(self, text: str) -> None:
        self.session.results_buffer.append(text)

    def get_last_result(self) -> str:
        if not self.session.results_buffer:
            return ""
        return self.session.results_buffer[-1]

    def _ensure_ready(self) -> None:
        if not self.session.is_ready or not self.launcher.is_ready():
            self.session.is_ready = False
            raise InfoStatError(
                code="SESSION_NOT_ACTIVE",
                message="InfoStat no esta activo. Llama a infostat_launch primero.",
            )

    @staticmethod
    def _detect_delimiter(file_path: Path) -> str:
        sample = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        first_line = sample[0] if sample else ""
        if ";" in first_line and "," not in first_line:
            return ";"
        return ","

    @staticmethod
    def _scan_csv(file_path: Path, delimiter: str, has_header: bool) -> tuple[int, list[str]]:
        with file_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            rows = list(reader)

        if not rows:
            return 0, []

        if has_header:
            header = rows[0]
            data_rows = rows[1:]
            return len(data_rows), header

        width = len(rows[0])
        columns = [f"col_{i+1}" for i in range(width)]
        return len(rows), columns
