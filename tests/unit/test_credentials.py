from unittest.mock import Mock

import pytest
from keyring.errors import KeyringError
from pydantic import SecretStr

from skill_dna_compiler.credentials import CredentialStoreError, KeyringCredentialStore


def test_keyring_store_saves_loads_and_deletes_without_exposing_value(monkeypatch):
    values: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.get_password",
        lambda service, account: values.get((service, account)),
    )
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.set_password",
        lambda service, account, value: values.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.delete_password",
        lambda service, account: values.pop((service, account)),
    )
    store = KeyringCredentialStore()
    secret = SecretStr("sk-proj-test-value-never-print")

    assert store.get_api_key() is None
    store.set_api_key(secret)
    loaded = store.get_api_key()
    assert loaded is not None
    assert loaded.get_secret_value() == secret.get_secret_value()
    assert secret.get_secret_value() not in str(loaded)
    assert store.delete_api_key() is True
    assert store.delete_api_key() is False


@pytest.mark.parametrize("operation", ["get_password", "set_password", "delete_password"])
def test_keyring_failures_return_safe_errors(monkeypatch, operation):
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.get_password",
        Mock(return_value="stored-value"),
    )
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.set_password",
        Mock(return_value=None),
    )
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.delete_password",
        Mock(return_value=None),
    )
    monkeypatch.setattr(
        f"skill_dna_compiler.credentials.keyring.{operation}",
        Mock(side_effect=KeyringError("backend detail must not escape")),
    )
    store = KeyringCredentialStore()

    with pytest.raises(CredentialStoreError) as exc_info:
        if operation == "get_password":
            store.get_api_key()
        elif operation == "set_password":
            store.set_api_key(SecretStr("sk-proj-test"))
        else:
            store.delete_api_key()

    assert "backend detail" not in str(exc_info.value)


def test_keyring_store_rejects_empty_key(monkeypatch):
    set_password = Mock()
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.set_password", set_password
    )

    with pytest.raises(ValueError, match="APIキーを入力"):
        KeyringCredentialStore().set_api_key(SecretStr("   "))

    set_password.assert_not_called()


def test_keyring_store_rejects_non_windows_backend(monkeypatch):
    class PlaintextBackend:
        pass

    set_password = Mock()
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.get_keyring", PlaintextBackend
    )
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.set_password", set_password
    )

    with pytest.raises(CredentialStoreError, match="安全なWindows資格情報ストア"):
        KeyringCredentialStore().set_api_key(SecretStr("sk-proj-test"))

    set_password.assert_not_called()
