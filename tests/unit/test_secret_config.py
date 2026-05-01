"""Unit tests for integration config credential encryption."""

from __future__ import annotations

import pytest

from urgp.services.secret_config import SecretConfigCodec, SecretConfigError, is_encrypted_value


def test_secret_config_codec_encrypts_sensitive_nested_values() -> None:
    codec = SecretConfigCodec("test-signing-key-for-secret-config-32chars")
    config = {
        "provider": "github",
        "credentials": {
            "authentication_token": "ghp_secret",
            "email": "dev@example.com",
        },
        "repositories": ["org/repo"],
    }

    encrypted = codec.encrypt_config(config)

    assert encrypted is not None
    credentials = encrypted["credentials"]
    assert isinstance(credentials, dict)
    assert is_encrypted_value(credentials["authentication_token"])
    assert credentials["authentication_token"] != "ghp_secret"
    assert credentials["email"] == "dev@example.com"
    assert codec.decrypt_config(encrypted) == config


def test_secret_config_codec_rejects_wrong_key() -> None:
    encrypted = SecretConfigCodec("test-signing-key-for-secret-config-32chars").encrypt_value("secret")

    with pytest.raises(SecretConfigError):
        SecretConfigCodec("different-signing-key-for-secret-config").decrypt_value(encrypted)

