from __future__ import annotations

import ctypes
import importlib
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

MUTEX_NAME = "Local\\SkillDNACompiler-v0.1"
ERROR_ALREADY_EXISTS = 183
PACKAGE_SMOKE_TEST_ENV = "SKILL_DNA_PACKAGE_SMOKE_TEST"
PACKAGE_SMOKE_TEST_OK = "SKILL_DNA_PACKAGE_IMPORTS_OK"
PACKAGED_REQUIRED_MODULES = (
    "streamlit.runtime.scriptrunner.magic_funcs",
    "skill_dna_compiler.config.settings",
    "skill_dna_compiler.credentials",
    "skill_dna_compiler.exporting",
    "skill_dna_compiler.extraction.openai_provider",
    "skill_dna_compiler.storage.repositories",
    "skill_dna_compiler.vault",
)


class AlreadyRunningError(RuntimeError):
    pass


@dataclass
class WindowsMutex:
    handle: int

    def close(self) -> None:
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = 0


def acquire_windows_mutex(name: str = MUTEX_NAME) -> WindowsMutex:
    if os.name != "nt":
        raise OSError("The Beta launcher supports Windows only.")
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        raise OSError("Skill DNA Compilerの起動ロックを作成できませんでした。")
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        raise AlreadyRunningError("Skill DNA Compilerは既に起動しています。")
    return WindowsMutex(handle=handle)


def find_free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def bundled_app_path() -> Path:
    return Path(__file__).resolve().with_name("app.py")


def streamlit_arguments(app_path: Path, port: int, *, headless: bool = False) -> list[str]:
    return [
        "streamlit",
        "run",
        str(app_path),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        f"--server.headless={'true' if headless else 'false'}",
        "--server.showEmailPrompt=false",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal",
        "--global.developmentMode=false",
    ]


def verify_packaged_imports() -> None:
    for module_name in PACKAGED_REQUIRED_MODULES:
        importlib.import_module(module_name)


def main() -> int:
    if os.environ.get(PACKAGE_SMOKE_TEST_ENV) == "1":
        verify_packaged_imports()
        print(PACKAGE_SMOKE_TEST_OK)
        return 0

    try:
        mutex = acquire_windows_mutex()
    except (AlreadyRunningError, OSError) as exc:
        print(f"[Skill DNA Compiler] {exc}")
        input("Enterキーを押して閉じてください。")
        return 1

    try:
        app_path = bundled_app_path()
        if not app_path.is_file():
            print("[Skill DNA Compiler] 同梱されたapp.pyが見つかりません。")
            input("Enterキーを押して閉じてください。")
            return 1

        os.environ["SKILL_DNA_ENVIRONMENT"] = "production"
        os.environ.pop("OPENAI_API_KEY", None)
        headless = os.environ.get("SKILL_DNA_LAUNCHER_HEADLESS") == "1"
        sys.argv = streamlit_arguments(
            app_path,
            find_free_loopback_port(),
            headless=headless,
        )
        from streamlit.web import cli as streamlit_cli

        return int(streamlit_cli.main() or 0)
    finally:
        mutex.close()


if __name__ == "__main__":
    raise SystemExit(main())
