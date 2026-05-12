"""Symmetric encryption for secrets stored in MongoDB.

Uses Fernet (AES-128-CBC with HMAC-SHA256) from the ``cryptography``
library.  The encryption key is read from the ``FIELD_ENCRYPTION_KEY``
environment variable.  If the key is not set, encrypt/decrypt are
**no-ops** — values pass through in plaintext (development mode).

Generate a valid key once::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Then store it in ``.env``::

    FIELD_ENCRYPTION_KEY=<base64-key>
"""

from __future__ import annotations

import os

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

_FERNET_INSTANCE = None
_INITIALISED = False


def _get_fernet():
    """Lazy-initialise the Fernet instance from env."""
    global _FERNET_INSTANCE, _INITIALISED  # noqa: PLW0603
    if _INITIALISED:
        return _FERNET_INSTANCE

    _INITIALISED = True
    key = os.environ.get("FIELD_ENCRYPTION_KEY")
    if not key:
        logger.warning(
            "[Encryption] FIELD_ENCRYPTION_KEY not set — secrets stored in plaintext"
        )
        return None

    try:
        from cryptography.fernet import Fernet

        _FERNET_INSTANCE = Fernet(key.encode())
        logger.info("[Encryption] Field encryption enabled")
    except Exception as exc:
        logger.error(
            "[Encryption] Invalid FIELD_ENCRYPTION_KEY: %s", exc, exc_info=True
        )
        _FERNET_INSTANCE = None

    return _FERNET_INSTANCE


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value.  Returns the ciphertext as a string.

    If encryption is not configured, returns the plaintext unchanged.
    """
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a previously-encrypted string.

    If encryption is not configured **or** the value is not valid
    Fernet ciphertext (e.g. legacy plaintext), returns the value
    unchanged so existing unencrypted data keeps working.
    """
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Value was stored before encryption was enabled — pass through.
        logger.debug("[Encryption] Value is not Fernet ciphertext — returning as-is")
        return ciphertext
