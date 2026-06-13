"""
Security utilities for JWT authentication.

Uses PyJWT (jpadilla/pyjwt) — actively maintained, replaces python-jose
which had unresolved CVE-2024-33664 (DoS) and CVE-2024-33663 (algorithm
confusion). API is near-identical so the migration is mechanical.
"""
from datetime import datetime, timedelta
from typing import Optional

import jwt
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


_JWT_ISSUER = "recruitai"
_JWT_AUDIENCE = "recruitai-api"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token with explicit issuer/audience binding."""
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    # iss/aud bind the token to this app — a leaked secret used by another
    # service can't mint tokens accepted here. iat/nbf/exp anchor the validity
    # window. The "sub" claim should be the user's UUID (set by callers).
    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": _JWT_ISSUER,
        "aud": _JWT_AUDIENCE,
    })
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[TokenData]:
    """Decode and validate JWT token. Verifies signature, exp, iat, iss, aud."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=_JWT_AUDIENCE,
            issuer=_JWT_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        if user_id is None:
            return None
        return TokenData(user_id=user_id, email=email)
    except PyJWTError:
        return None
