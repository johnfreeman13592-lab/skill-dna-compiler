import json
import sys

import pytest

from tools import run_bounded_streamlit as controller


def test_runtime_paths_must_be_distinct_and_share_project_run_directory(tmp_path):
    run_directory = tmp_path / "build" / "run"
    database = run_directory / "app.db"
    status = run_directory / "status.json"
    stop_file = run_directory / "stop.requested"
    stdout_log = run_directory / "stdout.log"
    stderr_log = run_directory / "stderr.log"

    controller._validate_runtime_paths(
        project_root=tmp_path,
        database=database,
        status=status,
        stop_file=stop_file,
        stdout_log=stdout_log,
        stderr_log=stderr_log,
    )

    with pytest.raises(ValueError, match="distinct"):
        controller._validate_runtime_paths(
            project_root=tmp_path,
            database=database,
            status=status,
            stop_file=database,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
        )
    with pytest.raises(ValueError, match="dedicated run directory"):
        controller._validate_runtime_paths(
            project_root=tmp_path,
            database=database,
            status=status,
            stop_file=stop_file,
            stdout_log=tmp_path / "elsewhere" / "stdout.log",
            stderr_log=stderr_log,
        )
    with pytest.raises(ValueError, match="below the project build directory"):
        controller._validate_runtime_paths(
            project_root=tmp_path,
            database=tmp_path.parent / "outside" / "app.db",
            status=tmp_path.parent / "outside" / "status.json",
            stop_file=tmp_path.parent / "outside" / "stop.requested",
            stdout_log=tmp_path.parent / "outside" / "stdout.log",
            stderr_log=tmp_path.parent / "outside" / "stderr.log",
        )

    project_root_run = tmp_path / "run"
    with pytest.raises(ValueError, match="below the project build directory"):
        controller._validate_runtime_paths(
            project_root=tmp_path,
            database=project_root_run / "app.db",
            status=project_root_run / "status.json",
            stop_file=project_root_run / "stop.requested",
            stdout_log=project_root_run / "stdout.log",
            stderr_log=project_root_run / "stderr.log",
        )


def test_runtime_paths_must_not_overwrite_existing_files(tmp_path):
    run_directory = tmp_path / "build" / "run"
    run_directory.mkdir(parents=True)
    stop_file = run_directory / "stop.requested"
    stop_file.write_text("preserve me", encoding="utf-8")

    with pytest.raises(ValueError, match="must not already exist"):
        controller._validate_runtime_paths(
            project_root=tmp_path,
            database=run_directory / "app.db",
            status=run_directory / "status.json",
            stop_file=stop_file,
            stdout_log=run_directory / "stdout.log",
            stderr_log=run_directory / "stderr.log",
        )

    assert stop_file.read_text(encoding="utf-8") == "preserve me"


def test_listener_remaining_after_cleanup_forces_failed_status_and_nonzero_exit(
    tmp_path,
    monkeypatch,
):
    run_directory = tmp_path / "build" / "run"
    status = run_directory / "status.json"
    argv = [
        "run_bounded_streamlit.py",
        "--project-root",
        str(tmp_path),
        "--database",
        str(run_directory / "app.db"),
        "--status",
        str(status),
        "--stop-file",
        str(run_directory / "stop.requested"),
        "--stdout-log",
        str(run_directory / "stdout.log"),
        "--stderr-log",
        str(run_directory / "stderr.log"),
        "--port",
        "54105",
        "--startup-timeout",
        "1",
        "--max-runtime",
        "2",
    ]

    class ExitedProcess:
        pid = 12345

        @staticmethod
        def poll():
            return 7

    port_results = iter((False, True, True))
    monotonic_results = iter((0.0, 0.0, 0.0, 6.0))
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(controller, "_port_is_open", lambda _port: next(port_results))
    monkeypatch.setattr(
        controller.time,
        "monotonic",
        lambda: next(monotonic_results),
    )
    monkeypatch.setattr(controller.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        controller.subprocess,
        "Popen",
        lambda *_args, **_kwargs: ExitedProcess(),
    )

    result = controller.main()
    final_status = json.loads(status.read_text(encoding="utf-8"))

    assert result == 6
    assert final_status["state"] == "failed"
    assert final_status["listener_after_cleanup"] is True
    assert "listener_remained_after_cleanup" in final_status["reason"]
