import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.core.config import settings



# ===== Key for Calculation Service =====
def get_internal_service_headers() -> dict:
    """
    Generate security headers for internal service-to-service communication.
    """
    return {
        "X-Internal-Key": settings.calc_service_key
    }



# ===== Password Hashing =====
def hash_password(plain_password: str) -> str:
    """Hash password memakai bcrypt. Simpan hasilnya (string) ke User.password_hash."""
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Bandingkan password plain dengan hash tersimpan. Return False bila hash rusak."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False



# ===== Refresh Token Helpers =====
def generate_refresh_token() -> str:
    """Buat refresh token acak (opaque). Nilai INI dikirim ke client, TIDAK disimpan mentah."""
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    """Hash refresh token untuk disimpan/dicari di tabel refresh_tokens (SHA-256 hex)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()



# ===== JWT =====
def _role_to_str(role) -> str:
    # role bisa berupa Enum(Role) atau string
    return role.value if hasattr(role, "value") else str(role)


def create_access_token(user) -> str:
    """Buat JWT access token dari objek User (atau apa pun dengan .id/.role/.department_id)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "role": _role_to_str(user.role),
        "department_id": user.department_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode & verifikasi JWT. Raise 401 bila expired/invalid."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )



# ===== Current User (principal ringan dari klaim JWT) =====
class CurrentUser(BaseModel):
    id: str
    role: str
    department_id: str | None = None


bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """Ambil principal dari access token. TIDAK query DB (role datang dari klaim)."""
    payload = decode_token(credentials.credentials)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
        )

    return CurrentUser(
        id=user_id,
        role=role,
        department_id=payload.get("department_id"),
    )



# ===== Authorization Guard (RBAC flat eksplisit) =====
def require_roles(*allowed_roles: str):
    """
    Dependency factory. Contoh:
        Depends(require_roles("superadmin"))
        Depends(require_roles("superadmin", "admin"))
    Menolak dengan 403 bila role principal tidak termasuk allowed_roles.
    """
    async def guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return guard