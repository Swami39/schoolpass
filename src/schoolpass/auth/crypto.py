from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from schoolpass.config import Settings


def _fernet(settings: Settings) -> Fernet:
    digest = hashlib.sha256(settings.secret_app_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(settings: Settings, plaintext: str) -> str:
    return _fernet(settings).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(settings: Settings, token: str) -> str:
    try:
        return _fernet(settings).decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt secret") from exc
