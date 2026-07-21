"""Cifrado reversible de credenciales de dispositivos."""

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from core.security import SECRET_KEY


ENCRYPTED_PREFIX = "enc:"


def _cipher() -> Fernet:
    material = os.getenv("TERMINAL_CREDENTIAL_KEY") or SECRET_KEY
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_credential(value: str) -> str:
    if not value or value.startswith(ENCRYPTED_PREFIX):
        return value
    token = _cipher().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_credential(value: str) -> str:
    if not value or not value.startswith(ENCRYPTED_PREFIX):
        return value
    try:
        return _cipher().decrypt(value[len(ENCRYPTED_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("No se pudo descifrar una credencial de terminal") from exc
