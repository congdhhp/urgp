"""Encryption helpers for product integration configuration.

Product Git and issue tracker configs can carry API tokens.  The public API
accepts those fields as JSON, but the control plane should not persist clear
text credentials in JSONB.
"""

from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Mapping
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ENCRYPTED_PREFIX = "enc:v1:"
_NONCE_SIZE_BYTES = 12
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authentication_token",
    "access_token",
    "client_secret",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
}


class SecretConfigError(ValueError):
    """Raised when an encrypted integration config cannot be decrypted."""


class SecretConfigCodec:
    """Encrypt and decrypt sensitive leaves in JSON-compatible configs."""

    def __init__(self, signing_key: str) -> None:
        self._aesgcm = AESGCM(hashlib.sha256(signing_key.encode("utf-8")).digest())

    def encrypt_config(self, config: Mapping[str, Any] | None) -> dict[str, Any] | None:
        """Return a copy of config with sensitive string values encrypted."""
        if config is None:
            return None
        return self._transform_mapping(config, encrypt=True)

    def decrypt_config(self, config: Mapping[str, Any] | None) -> dict[str, Any] | None:
        """Return a copy of config with encrypted string values decrypted."""
        if config is None:
            return None
        return self._transform_mapping(config, encrypt=False)

    def _transform_mapping(self, config: Mapping[str, Any], *, encrypt: bool) -> dict[str, Any]:
        transformed: dict[str, Any] = {}
        for key, value in config.items():
            transformed[key] = self._transform_value(key, value, encrypt=encrypt)
        return transformed

    def _transform_sequence(self, values: list[Any], *, encrypt: bool) -> list[Any]:
        return [self._transform_value("", value, encrypt=encrypt) for value in values]

    def _transform_value(self, key: str, value: Any, *, encrypt: bool) -> Any:
        if isinstance(value, Mapping):
            return self._transform_mapping(value, encrypt=encrypt)
        if isinstance(value, list):
            return self._transform_sequence(value, encrypt=encrypt)
        if isinstance(value, str):
            if encrypt and _is_sensitive_key(key) and value:
                return self.encrypt_value(value)
            if not encrypt and is_encrypted_value(value):
                return self.decrypt_value(value)
        return value

    def encrypt_value(self, value: str) -> str:
        """Encrypt a single string value unless it is already encrypted."""
        if is_encrypted_value(value):
            return value
        nonce = os.urandom(_NONCE_SIZE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, value.encode("utf-8"), None)
        token = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{_ENCRYPTED_PREFIX}{token}"

    def decrypt_value(self, value: str) -> str:
        """Decrypt one encrypted string value."""
        if not is_encrypted_value(value):
            return value
        token = value.removeprefix(_ENCRYPTED_PREFIX)
        try:
            encrypted = base64.urlsafe_b64decode(token.encode("ascii"))
            nonce = encrypted[:_NONCE_SIZE_BYTES]
            ciphertext = encrypted[_NONCE_SIZE_BYTES:]
            return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
        except (ValueError, InvalidTag) as exc:
            msg = "Encrypted integration configuration could not be decrypted with the current signing key."
            raise SecretConfigError(msg) from exc


def is_encrypted_value(value: str) -> bool:
    """Return True when value uses the URGP encrypted config envelope."""
    return value.startswith(_ENCRYPTED_PREFIX)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS


__all__ = [
    "SecretConfigCodec",
    "SecretConfigError",
    "is_encrypted_value",
]
