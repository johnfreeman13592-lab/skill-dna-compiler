"""Run a local Streamlit test server with a hard timeout and owned cleanup."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _write_status(path: Path, **values: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(values, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _port_is_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def _stop_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Start Streamlit for a bounded local browser test. The controller writes "
            "readiness to a status JSON file and always stops its owned process tree."
        )
    )
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    parser.add_argument("--stdout-log", type=Path, required=True)
    parser.add_argument("--stderr-log", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--startup-timeout", type=float, default=25.0)
    parser.add_argument("--max-runtime", type=float, default=180.0)
    args = parser.parse_args()
    if not 1 <= args.port <= 65_535:
        parser.error("--port must be between 1 and 65535")
    if not 1 <= args.startup_timeout <= 60:
        parser.error("--startup-timeout must be between 1 and 60 seconds")
    if not args.startup_timeout < args.max_runtime <= 600:
        parser.error(
            "--max-runtime must be greater than startup timeout and at most 600 seconds"
        )
    return args


def _validate_runtime_paths(
    *,
    project_root: Path,
    database: Path,
    status: Path,
    stop_file: Path,
    stdout_log: Path,
    stderr_log: Path,
) -> None:
    runtime_paths = (database, status, stop_file, stdout_log, stderr_log)
    if len(set(runtime_paths)) != len(runtime_paths):
        raise ValueError("database, status, stop, and log paths must be distinct")
    run_directory = status.parent
    build_root = project_root / "build"
    if run_directory == build_root or not run_directory.is_relative_to(build_root):
        raise ValueError(
            "the dedicated run directory must stay below the project build directory"
        )
    if any(path.parent != run_directory for path in runtime_paths):
        raise ValueError("all runtime files must share one dedicated run directory")
    if any(path.exists() for path in runtime_paths):
        raise ValueError("runtime files must not already exist")


def main() -> int:
    args = _parse_args()
    project_root = args.project_root.resolve()
    database = args.database.resolve()
    status = args.status.resolve()
    stop_file = args.stop_file.resolve()
    stdout_log = args.stdout_log.resolve()
    stderr_log = args.stderr_log.resolve()
    controller_pid = os.getpid()
    try:
        _validate_runtime_paths(
            project_root=project_root,
            database=database,
            status=status,
            stop_file=stop_file,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
        )
    except ValueError as exc:
        print(f"Invalid runtime paths: {exc}", file=sys.stderr)
        return 2

    if _port_is_open(args.port):
        _write_status(
            status,
            state="failed",
            reason="port_in_use",
            port=args.port,
            controller_pid=controller_pid,
        )
        return 2

    for path in (database, status, stop_file, stdout_log, stderr_log):
        path.parent.mkdir(parents=True, exist_ok=True)
    stop_file.unlink(missing_ok=True)

    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment["SKILL_DNA_DATABASE_PATH"] = str(database)
    environment["SKILL_DNA_ENVIRONMENT"] = "production"
    environment["PYTHONUNBUFFERED"] = "1"

    creation_flags = 0
    if os.name == "nt":
        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={args.port}",
        "--browser.gatherUsageStats=false",
        "--server.showEmailPrompt=false",
    ]
    process: subprocess.Popen[bytes] | None = None
    final_state = "failed"
    final_reason = "controller_error"
    exit_code = 1
    started_at = time.monotonic()

    try:
        with stdout_log.open("wb") as stdout_handle, stderr_log.open(
            "wb"
        ) as stderr_handle:
            process = subprocess.Popen(
                command,
                cwd=project_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                creationflags=creation_flags,
            )
            _write_status(
                status,
                state="starting",
                port=args.port,
                controller_pid=controller_pid,
                server_pid=process.pid,
                startup_timeout_seconds=args.startup_timeout,
                max_runtime_seconds=args.max_runtime,
            )

            startup_deadline = started_at + args.startup_timeout
            startup_result = "timeout"
            while time.monotonic() < startup_deadline:
                if stop_file.exists():
                    startup_result = "stop_requested"
                    break
                return_code = process.poll()
                if return_code is not None:
                    startup_result = f"server_exited_{return_code}"
                    break
                if _port_is_open(args.port):
                    startup_result = "ready"
                    break
                time.sleep(0.2)

            if startup_result == "stop_requested":
                final_state = "stopped"
                final_reason = "stop_requested_during_startup"
                exit_code = 0
            elif startup_result.startswith("server_exited_"):
                final_state = "failed"
                final_reason = startup_result
                exit_code = 3
            elif startup_result == "timeout":
                final_state = "failed"
                final_reason = "startup_timeout"
                exit_code = 4
            else:
                _write_status(
                    status,
                    state="ready",
                    port=args.port,
                    url=f"http://127.0.0.1:{args.port}",
                    controller_pid=controller_pid,
                    server_pid=process.pid,
                    max_runtime_seconds=args.max_runtime,
                )

                runtime_deadline = started_at + args.max_runtime
                runtime_result = "max_runtime_reached"
                while time.monotonic() < runtime_deadline:
                    if stop_file.exists():
                        runtime_result = "stop_requested"
                        break
                    return_code = process.poll()
                    if return_code is not None:
                        runtime_result = f"server_exited_{return_code}"
                        break
                    time.sleep(0.25)

                if runtime_result.startswith("server_exited_"):
                    final_state = "failed"
                    final_reason = runtime_result
                    exit_code = 5
                else:
                    final_state = "stopped"
                    final_reason = runtime_result
                    exit_code = 0
    except Exception as exc:
        final_state = "failed"
        final_reason = f"{type(exc).__name__}: {exc}"
        exit_code = 1
    finally:
        if process is not None:
            _stop_process_tree(process)
        cleanup_deadline = time.monotonic() + 5
        while _port_is_open(args.port) and time.monotonic() < cleanup_deadline:
            time.sleep(0.1)
        listener_after_cleanup = _port_is_open(args.port)
        if listener_after_cleanup:
            final_state = "failed"
            final_reason = f"{final_reason}; listener_remained_after_cleanup"
            exit_code = 6
        _write_status(
            status,
            state=final_state,
            reason=final_reason,
            port=args.port,
            controller_pid=controller_pid,
            server_pid=process.pid if process is not None else None,
            listener_after_cleanup=listener_after_cleanup,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
