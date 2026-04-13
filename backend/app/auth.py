import base64
import hashlib
import hmac
import json
import os
import time
import secrets

SECRET = os.getenv("OMS_JWT_SECRET", "dev-secret")
DEFAULT_USER = os.getenv("OMS_ADMIN_USER", "admin")
DEFAULT_PASS = os.getenv("OMS_ADMIN_PASS", "admin123")
DEFAULT_ROLE = os.getenv("OMS_ADMIN_ROLE", "admin")
USERS = {
    "admin": {"password": DEFAULT_PASS, "role": "admin"},
    "finance": {"password": os.getenv("OMS_FINANCE_PASS", "finance123"), "role": "finance"},
    "sales": {"password": os.getenv("OMS_SALES_PASS", "sales123"), "role": "sales"},
    "warehouse": {"password": os.getenv("OMS_WAREHOUSE_PASS", "warehouse123"), "role": "warehouse"},
}


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + pad).encode())


def create_token(username: str, role: str = DEFAULT_ROLE, ttl_seconds: int = 3600 * 8) -> str:
    payload = {"sub": username, "role": role, "exp": int(time.time()) + ttl_seconds}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).digest()
    return f"{_b64e(raw)}.{_b64e(sig)}"


def verify_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("invalid token")
    raw = _b64d(parts[0])
    sig = _b64d(parts[1])
    expected = hmac.new(SECRET.encode(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("invalid signature")
    payload = json.loads(raw.decode())
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("token expired")
    return payload


def login(username: str, password: str) -> str:
    user = USERS.get(username)
    if not user or password != user["password"]:
        raise ValueError("invalid credentials")
    return create_token(username, role=user["role"])


def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        # backward compatibility: old plain-text records
        return password == stored
    salt, digest = stored.split("$", 1)
    check = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return hmac.compare_digest(check, digest)
