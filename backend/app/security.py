import json
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings


class PayloadCipher:
    """Encrypts short-lived provider inputs; plaintext never enters ordinary logs or result records."""

    def __init__(self, settings: Settings):
        key = settings.execution_payload_encryption_key
        if key is None:
            raise RuntimeError("Execution payload encryption is not configured.")
        self._fernet = Fernet(key.get_secret_value().encode())

    @classmethod
    def is_configured(cls, settings: Settings) -> bool:
        try:
            cls(settings)
        except (RuntimeError, ValueError):
            return False
        return True

    def encrypt(self, payload: dict) -> str:
        return self._fernet.encrypt(json.dumps(payload, separators=(",", ":")).encode()).decode()

    def decrypt(self, token: str) -> dict:
        try:
            return json.loads(self._fernet.decrypt(token.encode()).decode())
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("The protected execution payload could not be read.") from exc


def payload_expiry(minutes: int = 30) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)
