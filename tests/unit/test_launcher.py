import os
import uuid
from pathlib import Path

import pytest

from skill_dna_compiler.launcher import (
    PACKAGED_REQUIRED_MODULES,
    AlreadyRunningError,
    acquire_windows_mutex,
    find_free_loopback_port,
    streamlit_arguments,
    verify_packaged_imports,
)


def test_streamlit_arguments_bind_only_to_loopback_without_external_python():
    arguments = streamlit_arguments(Path("C:/日本語 path/app.py"), 43123)

    assert arguments[:2] == ["streamlit", "run"]
    assert "--server.address=127.0.0.1" in arguments
    assert "--server.port=43123" in arguments
    assert "--server.showEmailPrompt=false" in arguments
    assert "--browser.gatherUsageStats=false" in arguments
    assert not any("python" in item.lower() for item in arguments)

    headless_arguments = streamlit_arguments(
        Path("C:/app.py"), 43124, headless=True
    )
    assert "--server.headless=true" in headless_arguments


def test_free_port_is_available_on_loopback():
    port = find_free_loopback_port()

    assert 0 < port <= 65535


def test_packaged_import_check_covers_streamlit_runtime_and_application_modules(
    monkeypatch,
):
    imported: list[str] = []
    monkeypatch.setattr(
        "skill_dna_compiler.launcher.importlib.import_module",
        lambda module_name: imported.append(module_name),
    )

    verify_packaged_imports()

    assert imported == list(PACKAGED_REQUIRED_MODULES)
    assert "streamlit.runtime.scriptrunner.magic_funcs" in imported
    assert "skill_dna_compiler.config.settings" in imported


@pytest.mark.skipif(os.name != "nt", reason="Windows named mutex test")
def test_windows_mutex_prevents_a_second_instance():
    name = f"Local\\SkillDNACompiler-test-{uuid.uuid4()}"
    first = acquire_windows_mutex(name)
    try:
        with pytest.raises(AlreadyRunningError):
            acquire_windows_mutex(name)
    finally:
        first.close()

    replacement = acquire_windows_mutex(name)
    replacement.close()
