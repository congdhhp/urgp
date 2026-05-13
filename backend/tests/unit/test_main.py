"""Unit tests for the application runner."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from urgp.main import run


def _settings(*, environment: str, debug: bool, workers: int = 4) -> MagicMock:
    settings = MagicMock()
    settings.environment = environment
    settings.debug = debug
    settings.host = "127.0.0.1"
    settings.port = 9001
    settings.workers = workers
    settings.log_level = "WARNING"
    return settings


class TestRun:
    def test_run_uses_production_safe_defaults(self) -> None:
        settings = _settings(environment="production", debug=False, workers=3)

        with patch("urgp.config.get_settings", return_value=settings), patch("uvicorn.run") as uvicorn_run:
            run()

        uvicorn_run.assert_called_once_with(
            "urgp.main:create_app",
            factory=True,
            host="127.0.0.1",
            port=9001,
            reload=False,
            workers=3,
            log_level="warning",
        )

    def test_run_forces_single_worker_when_reload_is_enabled(self) -> None:
        settings = _settings(environment="development", debug=True, workers=8)

        with patch("urgp.config.get_settings", return_value=settings), patch("uvicorn.run") as uvicorn_run:
            run()

        uvicorn_run.assert_called_once_with(
            "urgp.main:create_app",
            factory=True,
            host="127.0.0.1",
            port=9001,
            reload=True,
            workers=1,
            log_level="warning",
        )
