"""凭证加解密：模型 API Key 在数据库中以 Fernet 密文存储。

- 加密密钥优先取 ``settings.AI_CREDENTIAL_ENCRYPTION_KEY``（Fernet key 或任意口令）；
- 未配置时由 ``SECRET_KEY`` 派生，保证重启后仍能解密（仅适用于单机/开发）；
- 密文统一带 ``enc:v1:`` 前缀，读取时无前缀的值按历史明文兼容处理。
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .config import settings

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    raw = (settings.AI_CREDENTIAL_ENCRYPTION_KEY or "").strip()
    if raw:
        try:
            return Fernet(raw.encode("ascii"))
        except Exception:
            # 非标准 Fernet key：按口令派生
            digest = hashlib.sha256(raw.encode("utf-8")).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    digest = hashlib.sha256(("heritage-ai-credential:" + settings.SECRET_KEY).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    text = (plaintext or "").strip()
    if not text:
        return ""
    return _PREFIX + _fernet().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str:
    """解密凭证；兼容历史明文（无前缀）与解密失败（返回空串）。"""
    text = (value or "").strip()
    if not text:
        return ""
    if not text.startswith(_PREFIX):
        return text
    try:
        return _fernet().decrypt(text[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def secret_hint(value: str | None) -> str:
    """返回密钥提示（不泄露完整密钥）。"""
    plain = decrypt_secret(value)
    if not plain:
        return ""
    if len(plain) <= 4:
        return "*" * len(plain)
    return f"****{plain[-4:]}"
