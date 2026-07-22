from __future__ import annotations

import os
from typing import Protocol

import keyring
from keyring.errors import KeyringError
from pydantic import SecretStr

SERVICE_NAME = "Skill DNA Compiler"
ACCOUNT_NAME = "openai-api-key"


class CredentialStoreError(RuntimeError):
    """A safe, user-facing credential-store failure."""


class CredentialStore(Protocol):
    def get_api_key(self) -> SecretStr | None: ...

    def set_api_key(self, api_key: SecretStr) -> None: ...

    def delete_api_key(self) -> bool: ...


class KeyringCredentialStore:
    """Store the OpenAI API key in the operating system credential store."""

    def __init__(
        self,
        *,
        service_name: str = SERVICE_NAME,
        account_name: str = ACCOUNT_NAME,
    ) -> None:
        self.service_name = service_name
        self.account_name = account_name

    @staticmethod
    def _ensure_windows_backend() -> None:
        backend = keyring.get_keyring()
        if os.name != "nt" or type(backend).__module__ != "keyring.backends.Windows":
            raise CredentialStoreError(
                "安全なWindows資格情報ストアを利用できません。"
            )

    def get_api_key(self) -> SecretStr | None:
        self._ensure_windows_backend()
        try:
            value = keyring.get_password(self.service_name, self.account_name)
        except KeyringError:
            raise CredentialStoreError(
                "Windows資格情報ストアからAPIキーを読み込めませんでした。"
            ) from None
        if value is None or not value.strip():
            return None
        return SecretStr(value)

    def set_api_key(self, api_key: SecretStr) -> None:
        value = api_key.get_secret_value().strip()
        if not value:
            raise ValueError("APIキーを入力してください。")
        self._ensure_windows_backend()
        try:
            keyring.set_password(self.service_name, self.account_name, value)
        except KeyringError:
            raise CredentialStoreError(
                "Windows資格情報ストアへAPIキーを保存できませんでした。"
            ) from None

    def delete_api_key(self) -> bool:
        self._ensure_windows_backend()
        try:
            existing = keyring.get_password(self.service_name, self.account_name)
            if existing is None:
                return False
            keyring.delete_password(self.service_name, self.account_name)
        except KeyringError:
            raise CredentialStoreError(
                "Windows資格情報ストアからAPIキーを削除できませんでした。"
            ) from None
        return True
