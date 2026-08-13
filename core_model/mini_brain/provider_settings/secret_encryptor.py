"""MB-27: Secret Encryptor -- the one documented, explicitly-permitted
exception to this package's otherwise-pure rule (the phase spec itself
carves this out: "Pure modules must not import ... except the
dedicated encryptor module that reads the environment key").

This module reads `os.environ[SECRET_ENCRYPTION_KEY_ENV_VAR]` and,
given that key, performs real `cryptography.fernet.Fernet` encrypt/
decrypt calls -- CPU-only cryptographic computation, never a database
write, never a network call, never a subprocess. If the key is
missing, `encryption_available()` returns `False` and
`encrypt_secret()`/`decrypt_secret()` raise `EncryptionUnavailableError`
rather than ever falling back to storing plaintext or silently
generating and persisting a new key -- the spec is explicit: "Never
auto-generate and silently persist a key."

Fernet.encrypt() produces a URL-safe base64 *bytes* token that is
genuine ASCII text (verified directly against a real key during this
phase's implementation) -- `encrypt_secret()` therefore returns `str`
(the natural TEXT-column-compatible type), and `decrypt_secret()`
accepts `str`, encoding/decoding to/from `ascii` internally.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

SECRET_ENCRYPTION_KEY_ENV_VAR = "BRUD_SECRET_ENCRYPTION_KEY"


class EncryptionUnavailableError(Exception):
    """Raised when BRUD_SECRET_ENCRYPTION_KEY is not configured. Never
    caught-and-silently-worked-around by generating a key -- the caller
    must surface this as a real, honest failure."""


class SecretDecryptionError(Exception):
    """Raised when a stored encrypted value cannot be decrypted with
    the currently-configured key (wrong/rotated key, or tampered/
    corrupted data) -- never silently returns garbage plaintext."""


def encryption_available() -> bool:
    return bool(os.environ.get(SECRET_ENCRYPTION_KEY_ENV_VAR))


def _fernet() -> Fernet:
    raw_key = os.environ.get(SECRET_ENCRYPTION_KEY_ENV_VAR)
    if not raw_key:
        raise EncryptionUnavailableError(
            f"{SECRET_ENCRYPTION_KEY_ENV_VAR} is not configured in this environment"
        )
    return Fernet(raw_key.encode("ascii"))


def encrypt_secret(plaintext_value: str) -> str:
    token = _fernet().encrypt(plaintext_value.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(encrypted_value: str) -> str:
    try:
        plaintext_bytes = _fernet().decrypt(encrypted_value.encode("ascii"))
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "stored secret could not be decrypted with the currently-configured key"
        ) from exc
    return plaintext_bytes.decode("utf-8")
