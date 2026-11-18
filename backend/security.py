"""Password hashing (scrypt, standard library), login tokens (JWT) and a small rate limiter."""
import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Optional

import jwt

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 15, 8, 1
TOKEN_DAYS = int(os.getenv("TOKEN_DAYS", "30"))


def _require_scrypt() -> None:
    """Fail at startup, not at the first sign-in, if this Python cannot hash passwords."""
    if not hasattr(hashlib, "scrypt"):
        raise RuntimeError(
            "This Python has no hashlib.scrypt (it was built without OpenSSL 1.1+, e.g. macOS's "
            "/usr/bin/python3 with LibreSSL). Recreate the venv with Python 3.10+ from python.org, "
            "Homebrew or conda."
        )


_require_scrypt()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                         maxmem=64 * 1024 * 1024, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    """False for a wrong password or a malformed stored hash. Server problems are raised, not hidden."""
    if not isinstance(stored, str):
        return False
    try:
        algo, n, r, p, salt, expected = stored.split("$")
        if algo != "scrypt":
            return False
        key = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             maxmem=64 * 1024 * 1024, dklen=32)
        return hmac.compare_digest(key, base64.b64decode(expected))
    except (ValueError, TypeError):  # bad field count, non-numeric n/r/p, bad base64 (binascii.Error), bad scrypt params
        return False


_dummy_hash = None


def burn_time(password: str) -> None:
    """Do the same hashing work for an unknown email, so response time does not reveal which emails exist."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    verify_password(password, _dummy_hash)


_secret_cache = None


def _secret() -> str:
    """JWT_SECRET from the environment. For local development one is generated and kept in .jwt_secret."""
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    env = os.getenv("JWT_SECRET")
    if env:
        _secret_cache = env
        return env
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".jwt_secret")
    if os.path.exists(path):
        with open(path) as fh:
            _secret_cache = fh.read().strip()
    else:
        _secret_cache = secrets.token_urlsafe(48)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(_secret_cache)
    return _secret_cache


def make_token(user_id: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + TOKEN_DAYS * 86400}, _secret(), algorithm="HS256")


def read_token(token: str) -> Optional[int]:
    try:
        return int(jwt.decode(token, _secret(), algorithms=["HS256"])["sub"])
    except Exception:
        return None


class RateLimiter:
    """Allow `limit` hits per `window` seconds for each key (in memory, per server process)."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True