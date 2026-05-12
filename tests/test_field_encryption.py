"""Tests for the field_encryption module."""

from __future__ import annotations

from unittest.mock import patch

import pytest


_MODULE = "crewai_productfeature_planner.services.field_encryption"


class TestEncryptDecryptNoKey:
    """When FIELD_ENCRYPTION_KEY is not set, values pass through unchanged."""

    def test_encrypt_passthrough(self):
        with patch(f"{_MODULE}._INITIALISED", False), \
             patch(f"{_MODULE}._FERNET_INSTANCE", None), \
             patch.dict("os.environ", {}, clear=False):
            # Remove key if set
            import os
            os.environ.pop("FIELD_ENCRYPTION_KEY", None)
            # Reset the lazy init state
            import crewai_productfeature_planner.services.field_encryption as mod
            mod._INITIALISED = False
            mod._FERNET_INSTANCE = None

            assert mod.encrypt_value("hello") == "hello"

    def test_decrypt_passthrough(self):
        import crewai_productfeature_planner.services.field_encryption as mod
        mod._INITIALISED = False
        mod._FERNET_INSTANCE = None
        import os
        os.environ.pop("FIELD_ENCRYPTION_KEY", None)

        assert mod.decrypt_value("hello") == "hello"


class TestEncryptDecryptWithKey:
    """When FIELD_ENCRYPTION_KEY is set, values are encrypted and decryptable."""

    def test_roundtrip(self):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()

        import crewai_productfeature_planner.services.field_encryption as mod
        mod._INITIALISED = False
        mod._FERNET_INSTANCE = None

        with patch.dict("os.environ", {"FIELD_ENCRYPTION_KEY": key}):
            encrypted = mod.encrypt_value("secret_token")
            assert encrypted != "secret_token"

            # Reset to re-init with same key
            mod._INITIALISED = False
            mod._FERNET_INSTANCE = None

            decrypted = mod.decrypt_value(encrypted)
            assert decrypted == "secret_token"

    def test_decrypt_legacy_plaintext_returns_unchanged(self):
        """Pre-encryption plaintext values should pass through safely."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()

        import crewai_productfeature_planner.services.field_encryption as mod
        mod._INITIALISED = False
        mod._FERNET_INSTANCE = None

        with patch.dict("os.environ", {"FIELD_ENCRYPTION_KEY": key}):
            result = mod.decrypt_value("ghp_plaintext_token")
            assert result == "ghp_plaintext_token"

    def test_invalid_key_falls_back(self):
        """An invalid key should not crash — just disable encryption."""
        import crewai_productfeature_planner.services.field_encryption as mod
        mod._INITIALISED = False
        mod._FERNET_INSTANCE = None

        with patch.dict("os.environ", {"FIELD_ENCRYPTION_KEY": "not-valid-base64"}):
            result = mod.encrypt_value("hello")
            assert result == "hello"
