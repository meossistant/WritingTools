"""
Secure API key storage for Writing Tools (Issue #206).

Supports three zero-dependency layers:
1. Environment variable references (`env:VAR_NAME`) — resolved dynamically at runtime
   without ever persisting the secret to `config.json`.
2. Windows DPAPI (`dpapi:<base64>`) — OS-native per-user encryption via `crypt32.dll`
   on Windows systems.
3. Authenticated local encryption (`enc2:<base64(salt + ciphertext + hmac)>`) —
   uses a per-user 256-bit random key stored with `0600` permissions in
   `<data_dir>/.secret_key` with PBKDF2-HMAC-SHA256 key derivation, SHA-256 CTR
   stream encryption, and HMAC-SHA256 integrity verification (Linux / fallback).

Legacy `enc:` (XOR+Base64) and plaintext values remain readable for seamless
backward-compatible migration.
"""

from __future__ import annotations

import base64
import binascii
import ctypes
import hashlib
import hmac
import logging
import os
import secrets as _stdlib_secrets
import sys
from typing import Optional

from writing_tools.paths import get_data_dir

ENV_PREFIX = "env:"
DPAPI_PREFIX = "dpapi:"
ENC2_PREFIX = "enc2:"
LEGACY_XOR_PREFIX = "enc:"

_LEGACY_XOR_KEY = 0x5A
_KEY_FILENAME = ".secret_key"
_SALT_LEN = 16
_MAC_LEN = 32


def is_env_reference(value: str) -> bool:
    """Return True if value is an `env:VAR_NAME` reference."""
    return isinstance(value, str) and value.startswith(ENV_PREFIX) and len(value) > len(ENV_PREFIX)


def resolve_env_reference(value: str) -> str:
    """Resolve `env:VAR_NAME` from `os.environ` (returns empty string if unset)."""
    if not is_env_reference(value):
        return value or ""
    var_name = value[len(ENV_PREFIX) :].strip()
    if not var_name:
        return ""
    return os.environ.get(var_name, "")


def _get_or_create_master_key(key_dir: Optional[str] = None) -> bytes:
    """
    Load or generate a 32-byte per-user master key stored with `0600` permissions.
    """
    base_dir = key_dir or get_data_dir()
    os.makedirs(base_dir, exist_ok=True)
    key_path = os.path.join(base_dir, _KEY_FILENAME)

    if os.path.exists(key_path):
        try:
            with open(key_path, "rb") as f:
                raw = f.read()
            if len(raw) >= 32:
                return raw[:32]
        except OSError as e:
            logging.warning(f"Could not read secret key file {key_path}: {e}")

    master_key = _stdlib_secrets.token_bytes(32)
    try:
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, master_key)
        finally:
            os.close(fd)
        if not sys.platform.startswith("win32"):
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
    except OSError as e:
        logging.warning(f"Could not persist secret key file {key_path}: {e}")
    return master_key


def _keystream(enc_key: bytes, salt: bytes, length: int) -> bytes:
    """Generate a deterministic SHA-256 CTR keystream of `length` bytes."""
    chunks = []
    produced = 0
    counter = 0
    while produced < length:
        block = hashlib.sha256(enc_key + salt + counter.to_bytes(4, "big")).digest()
        chunks.append(block)
        produced += len(block)
        counter += 1
    return b"".join(chunks)[:length]


def _encrypt_enc2(plaintext: str, key_dir: Optional[str] = None) -> str:
    """Encrypt plaintext with per-user master key using CTR-SHA256 + HMAC-SHA256."""
    master_key = _get_or_create_master_key(key_dir=key_dir)
    salt = _stdlib_secrets.token_bytes(_SALT_LEN)
    derived = hashlib.pbkdf2_hmac("sha256", master_key, salt, 100_000, dklen=64)
    enc_key, mac_key = derived[:32], derived[32:]

    pt_bytes = plaintext.encode("utf-8")
    stream = _keystream(enc_key, salt, len(pt_bytes))
    ciphertext = bytes(a ^ b for a, b in zip(pt_bytes, stream))
    mac = hmac.new(mac_key, salt + ciphertext, hashlib.sha256).digest()
    payload = base64.b64encode(salt + ciphertext + mac).decode("ascii")
    return ENC2_PREFIX + payload


def _decrypt_enc2(encoded_value: str, key_dir: Optional[str] = None) -> str:
    """Decrypt and authenticate an `enc2:` secret."""
    payload_b64 = encoded_value[len(ENC2_PREFIX) :]
    try:
        blob = base64.b64decode(payload_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        logging.warning(f"Malformed enc2 secret (base64 error): {e}")
        return ""

    if len(blob) < _SALT_LEN + _MAC_LEN:
        logging.warning("Malformed enc2 secret (too short)")
        return ""

    salt = blob[:_SALT_LEN]
    mac = blob[-_MAC_LEN:]
    ciphertext = blob[_SALT_LEN:-_MAC_LEN]

    master_key = _get_or_create_master_key(key_dir=key_dir)
    derived = hashlib.pbkdf2_hmac("sha256", master_key, salt, 100_000, dklen=64)
    enc_key, mac_key = derived[:32], derived[32:]

    expected_mac = hmac.new(mac_key, salt + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        logging.warning("enc2 secret failed HMAC verification; key mismatch or corruption")
        return ""

    stream = _keystream(enc_key, salt, len(ciphertext))
    pt_bytes = bytes(a ^ b for a, b in zip(ciphertext, stream))
    try:
        return pt_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        logging.warning(f"Failed to decode decrypted enc2 secret: {e}")
        return ""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _dpapi_protect(plaintext: str) -> Optional[str]:
    """Encrypt plaintext using Windows DPAPI (`CryptProtectData`)."""
    if not sys.platform.startswith("win32"):
        return None
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        data = plaintext.encode("utf-8")
        buf = (ctypes.c_ubyte * len(data))(*data)
        in_blob = _DataBlob(len(data), buf)
        out_blob = _DataBlob()
        # CRYPTPROTECT_UI_FORBIDDEN = 0x01
        if not crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "WritingTools",
            None,
            None,
            None,
            0x01,
            ctypes.byref(out_blob),
        ):
            return None
        try:
            encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return DPAPI_PREFIX + base64.b64encode(encrypted).decode("ascii")
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception as e:
        logging.warning(f"Windows DPAPI protection failed, falling back to enc2: {e}")
        return None


def _dpapi_unprotect(encoded_value: str) -> str:
    """Decrypt a `dpapi:` secret using Windows DPAPI (`CryptUnprotectData`)."""
    if not sys.platform.startswith("win32"):
        logging.warning("Cannot decrypt Windows DPAPI secret on non-Windows platform")
        return ""
    try:
        raw = base64.b64decode(encoded_value[len(DPAPI_PREFIX) :], validate=True)
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = (ctypes.c_ubyte * len(raw))(*raw)
        in_blob = _DataBlob(len(raw), buf)
        out_blob = _DataBlob()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0x01,
            ctypes.byref(out_blob),
        ):
            logging.warning("Windows DPAPI CryptUnprotectData failed")
            return ""
        try:
            decrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return decrypted.decode("utf-8")
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception as e:
        logging.warning(f"Failed to decrypt DPAPI secret: {e}")
        return ""


def _decrypt_legacy_xor(encoded_value: str) -> str:
    """Decrypt legacy `enc:` XOR+Base64 obfuscated API keys."""
    encoded = encoded_value[len(LEGACY_XOR_PREFIX) :]
    try:
        xored = base64.b64decode(encoded, validate=True)
        return bytes(b ^ _LEGACY_XOR_KEY for b in xored).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError) as e:
        logging.warning(f"Failed to decode legacy enc: API key: {e}")
        return ""


def is_protected_secret(value: str) -> bool:
    """Return True if value is already protected (`env:`, `dpapi:`, or `enc2:`)."""
    if not value:
        return True
    return value.startswith((ENV_PREFIX, DPAPI_PREFIX, ENC2_PREFIX))


def protect_secret(value: str, key_dir: Optional[str] = None) -> str:
    """
    Protect an API key before persisting to `config.json`:
    - Empty strings and `env:VAR_NAME` references are returned as-is.
    - Already-protected `dpapi:` / `enc2:` values are returned unchanged.
    - Legacy `enc:` values are upgraded to strong protection.
    - Plaintext values are encrypted with Windows DPAPI (on Windows) or `enc2:` (Linux/fallback).
    """
    if not value:
        return ""
    if value.startswith((ENV_PREFIX, DPAPI_PREFIX, ENC2_PREFIX)):
        return value
    plaintext = _decrypt_legacy_xor(value) if value.startswith(LEGACY_XOR_PREFIX) else value
    if not plaintext:
        return ""
    dpapi = _dpapi_protect(plaintext)
    if dpapi is not None:
        return dpapi
    return _encrypt_enc2(plaintext, key_dir=key_dir)


def unprotect_secret(
    stored_value: str,
    *,
    resolve_env: bool = False,
    key_dir: Optional[str] = None,
) -> str:
    """
    Unprotect a persisted API key value.

    - When `resolve_env=False` (default, for Settings UI display): `env:VAR_NAME` is
      returned verbatim so the user sees and preserves their env-var reference.
    - When `resolve_env=True` (for runtime provider initialization): `env:VAR_NAME`
      is resolved from `os.environ`.
    - Decrypts `dpapi:`, `enc2:`, and legacy `enc:` transparently; returns plaintext as-is.
    """
    if not stored_value:
        return ""
    if stored_value.startswith(ENV_PREFIX):
        return resolve_env_reference(stored_value) if resolve_env else stored_value
    if stored_value.startswith(DPAPI_PREFIX):
        return _dpapi_unprotect(stored_value)
    if stored_value.startswith(ENC2_PREFIX):
        return _decrypt_enc2(stored_value, key_dir=key_dir)
    if stored_value.startswith(LEGACY_XOR_PREFIX):
        return _decrypt_legacy_xor(stored_value)
    return stored_value
