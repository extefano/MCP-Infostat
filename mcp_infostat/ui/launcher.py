from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from mcp_infostat.errors import InfoStatError

try:
    from pywinauto import Application
    from pywinauto.timings import wait_until_passes
except Exception:  # pragma: no cover - se valida en runtime
    Application = None  # type: ignore[assignment]
    wait_until_passes = None  # type: ignore[assignment]


class InfoStatLauncher:
    def __init__(self, default_exe_path: str):
        self.default_exe_path = default_exe_path
        self._app: Application | None = None
        self._process: subprocess.Popen[Any] | None = None
        self._backend: str | None = None

    def launch(self, exe_path: str | None = None, timeout: float = 30) -> dict[str, Any]:
        if Application is None or wait_until_passes is None:
            raise InfoStatError(
                code="DEPENDENCY_MISSING",
                message="pywinauto no esta disponible en el entorno actual.",
            )

        effective_path = Path(exe_path or self.default_exe_path)
        if not effective_path.exists():
            raise InfoStatError(
                code="INFOSTAT_EXE_NOT_FOUND",
                message="No se encontro el ejecutable de InfoStat.",
                details={"path": str(effective_path)},
            )

        self._process = subprocess.Popen([str(effective_path)])
        backend_errors: dict[str, str] = {}
        self._app = None
        self._backend = None

        for backend in ("uia", "win32"):
            candidate_app = Application(backend=backend)

            def _connect() -> None:
                candidate_app.connect(process=self._process.pid)

            try:
                wait_until_passes(timeout=timeout, retry_interval=0.5, func=_connect)
                self._app = candidate_app
                self._backend = backend
                break
            except Exception as exc:
                backend_errors[backend] = str(exc)

        if self._app is None:
            if self._process.poll() is None:
                self._process.terminate()
                self._process.wait(timeout=10)
            raise InfoStatError(
                code="INFOSTAT_LAUNCH_TIMEOUT",
                message="Timeout esperando que InfoStat quede disponible.",
                details={"timeout_seconds": timeout, "backend_errors": backend_errors},
            )

        return {"pid": self._process.pid, "backend": self._backend}

    def is_ready(self) -> bool:
        if self._app is None or self._process is None:
            return False
        if self._process.poll() is not None:
            return False
        return True

    def close(self, save_before_close: bool = False) -> None:
        if self._process is None:
            return

        # En Sprint 1 no se automatiza dialogo de guardado; se cierra el proceso.
        if self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=10)

        self._process = None
        self._app = None
        self._backend = None

    def load_file_via_keyboard(self, file_path: Path, timeout: float = 10.0) -> bool:
        if wait_until_passes is None or self._app is None or not self.is_ready():
            raise InfoStatError(
                code="INFOSTAT_UI_NOT_READY",
                message="InfoStat no esta listo para carga de datos via teclado.",
            )

        if not file_path.exists():
            raise InfoStatError(
                code="DATA_FILE_NOT_FOUND",
                message="No se encontro el archivo a cargar en InfoStat.",
                details={"file_path": str(file_path)},
            )

        main_window = self._get_main_window(timeout=timeout)
        try:
            main_window.set_focus()
        except Exception:
            # En algunas ventanas Delphi set_focus puede fallar aunque la ventana este activa.
            pass

        open_dialog: Any | None = None
        last_error = ""
        shortcuts: list[tuple[str, ...]] = [
            ("^o",),
            ("%a", "a"),
            ("%f", "o"),
            ("%f", "a"),
        ]

        for sequence in shortcuts:
            try:
                for keys in sequence:
                    main_window.type_keys(keys, set_foreground=True)

                def _wait_open_dialog() -> None:
                    nonlocal open_dialog
                    open_dialog = self._find_open_dialog()

                wait_until_passes(timeout=2.5, retry_interval=0.2, func=_wait_open_dialog)
                break
            except Exception as exc:
                last_error = str(exc)
                open_dialog = None

        if open_dialog is None:
            raise InfoStatError(
                code="DATA_LOAD_UI_FAILED",
                message="No se pudo abrir el dialogo de archivo en InfoStat usando atajos de teclado.",
                details={
                    "file_path": str(file_path),
                    "backend": self._backend,
                    "shortcuts": [" -> ".join(keys) for keys in shortcuts],
                    "last_error": last_error,
                },
            )

        try:
            used_edit_control = False

            if hasattr(open_dialog, "child_window"):
                try:
                    edit = open_dialog.child_window(class_name="Edit")
                    if edit.exists(timeout=0.5):
                        edit.set_edit_text(str(file_path))
                        used_edit_control = True
                except Exception:
                    used_edit_control = False

            if not used_edit_control:
                try:
                    open_dialog.set_focus()
                except Exception:
                    pass
                open_dialog.type_keys("^a{BACKSPACE}", set_foreground=True)
                open_dialog.type_keys(str(file_path), with_spaces=True, set_foreground=True)

            open_dialog.type_keys("{ENTER}", set_foreground=True)
        except Exception as exc:
            raise InfoStatError(
                code="DATA_LOAD_UI_FAILED",
                message="No se pudo completar la carga del archivo en el dialogo de InfoStat.",
                details={
                    "file_path": str(file_path),
                    "backend": self._backend,
                    "raw": str(exc),
                },
            ) from exc

        return True

    def _get_main_window(self, timeout: float) -> Any:
        assert self._app is not None
        assert wait_until_passes is not None

        main_window: Any | None = None

        def _locate() -> None:
            nonlocal main_window
            windows = list(self._app.windows())

            for window in windows:
                if not self._is_splash_window(window):
                    main_window = window
                    return

            if windows:
                top = self._app.top_window()
                if not self._is_splash_window(top):
                    main_window = top
                    return

            raise RuntimeError("main_window_not_ready")

        wait_until_passes(timeout=timeout, retry_interval=0.3, func=_locate)

        if main_window is None:
            raise InfoStatError(
                code="INFOSTAT_UI_NOT_READY",
                message="No se pudo detectar la ventana principal de InfoStat.",
                details={"backend": self._backend},
            )

        return main_window

    def _find_open_dialog(self) -> Any:
        assert self._app is not None

        for window in self._app.windows():
            title = (window.window_text() or "").strip().lower()
            class_name = (window.class_name() or "").strip().lower()
            if class_name == "#32770":
                return window
            if "abrir" in title or "open" in title:
                return window

        raise RuntimeError("open_dialog_not_found")

    @staticmethod
    def _is_splash_window(window: Any) -> bool:
        title = (window.window_text() or "").strip().lower()
        class_name = (window.class_name() or "").strip().lower()
        return class_name == "tstartupscreen" or "acerca" in title
