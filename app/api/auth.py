import time

import jwt

from app.config import settings


def create_token(subject: str, org_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "org_id": org_id,
        "iat": now,
        "exp": now + settings.jwt_expire_minutes * 60,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
