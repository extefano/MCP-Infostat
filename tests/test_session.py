from pathlib import Path

import pytest

from mcp_infostat.config import AppConfig, InfoStatConfig, MCPConfig, PathsConfig, SecurityConfig, TimeoutsConfig
from mcp_infostat.errors import InfoStatError
from mcp_infostat.session import InfoStatSessionManager


class FakeLauncher:
    def __init__(self) -> None:
        self._ready = False
        self._pid = 4242
        self._backend = "win32"
        self.keyboard_success = True
        self.keyboard_calls = 0

    def launch(self, exe_path: str | None = None, timeout: float = 30) -> dict[str, int | str]:
        self._ready = True
        return {"pid": self._pid, "backend": self._backend}

    def is_ready(self) -> bool:
        return self._ready

    def close(self, save_before_close: bool = False) -> None:
        self._ready = False

    def load_file_via_keyboard(self, file_path: Path, timeout: float = 10.0) -> bool:
        self.keyboard_calls += 1
        return self.keyboard_success


@pytest.fixture()
def manager(tmp_path: Path) -> InfoStatSessionManager:
    config = AppConfig(
        infostat=InfoStatConfig(exe_path="C:/Program Files/InfoStat/InfoStat.exe"),
        paths=PathsConfig(data_base_dir=tmp_path, results_base_dir=tmp_path / "results"),
        timeouts=TimeoutsConfig(),
        mcp=MCPConfig(transport="stdio"),
        security=SecurityConfig(allowed_extensions=[".csv", ".txt"], max_file_size_mb=10),
    )
    return InfoStatSessionManager(config=config, launcher=FakeLauncher())


def test_launch_status_close_cycle(manager: InfoStatSessionManager) -> None:
    launched = manager.launch()
    assert launched["running"] is True
    assert launched["ui_backend"] == "win32"

    status = manager.status()
    assert status["running"] is True
    assert status["dataset_loaded"] is False
    assert status["ui_backend"] == "win32"

    closed = manager.close()
    assert closed["running"] is False


def test_data_load_and_get_info_csv(manager: InfoStatSessionManager, tmp_path: Path) -> None:
    manager.launch()
    dataset = tmp_path / "test.csv"
    dataset.write_text("Tratamiento,Rendimiento\nA,10\nB,20\n", encoding="utf-8")

    loaded = manager.data_load(file_path=dataset, sheet_name=None, delimiter=None, has_header=True)
    assert loaded["rows"] == 2
    assert loaded["cols"] == 2
    assert loaded["mode"] == "ui_keyboard"
    assert loaded["ui_loaded"] is True
    assert manager.launcher.keyboard_calls == 1

    info = manager.data_get_info()
    assert info["n_rows"] == 2
    assert info["n_cols"] == 2
    assert info["columns"] == ["Tratamiento", "Rendimiento"]


def test_data_load_requires_active_session(manager: InfoStatSessionManager, tmp_path: Path) -> None:
    dataset = tmp_path / "test.csv"
    dataset.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(InfoStatError) as exc_info:
        manager.data_load(file_path=dataset, sheet_name=None, delimiter=None, has_header=True)

    assert exc_info.value.code == "SESSION_NOT_ACTIVE"


def test_data_load_raises_when_keyboard_strategy_fails(manager: InfoStatSessionManager, tmp_path: Path) -> None:
    manager.launcher.keyboard_success = False
    manager.launch()

    dataset = tmp_path / "test.csv"
    dataset.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(InfoStatError) as exc_info:
        manager.data_load(file_path=dataset, sheet_name=None, delimiter=None, has_header=True)

    assert manager.launcher.keyboard_calls == 1
    assert exc_info.value.code == "DATA_LOAD_UI_FAILED"
