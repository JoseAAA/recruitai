"""
Authentication API Routes with PostgreSQL persistence.
Login, register, and user management endpoints.
"""
import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limit
from app.core.security import (
    Token,
    TokenData,
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.privacy import AuditLogger, get_audit_logger
from app.db.models import UserDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ============ Request/Response Schemas ============

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Mínimo 8 caracteres")
    full_name: str = Field(..., min_length=2, max_length=120)


class LoginCredentials(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# Strict bodies for self-service updates. Listed explicitly so a recruiter
# cannot escalate to admin or change is_active / role via mass-assignment.
class UpdateMeRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


class AdminUpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|recruiter)$")


class AdminUpdateStatusRequest(BaseModel):
    is_active: bool


# ============ Database Helper Functions ============

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[UserDB]:
    """Get user by email from database."""
    result = await db.execute(select(UserDB).where(UserDB.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[UserDB]:
    """Get user by ID from database."""
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[UserDB]:
    """Authenticate user with email and password."""
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def ensure_default_users(db: AsyncSession):
    """Ensure default admin and HR users exist in database.
    Passwords are read from environment variables (ADMIN_INITIAL_PASSWORD / RECRUITER_INITIAL_PASSWORD).
    """
    admin_password = settings.ADMIN_INITIAL_PASSWORD
    recruiter_password = settings.RECRUITER_INITIAL_PASSWORD

    # Insecure-default check is centralized in core.config.Settings, which
    # hard-fails in production. We don't repeat the warning here to keep
    # startup logs clean — the seed only runs the first time anyway.

    # Check if admin exists
    admin = await get_user_by_email(db, "admin@recruitai.com")
    if not admin:
        admin = UserDB(
            id=uuid4(),
            email="admin@recruitai.com",
            full_name="Admin User",
            role="admin",
            is_active=True,
            hashed_password=get_password_hash(admin_password),
        )
        db.add(admin)
        logger.info("Created default admin user: admin@recruitai.com")

    # Check if HR user exists
    hr_user = await get_user_by_email(db, "rrhh@recruitai.com")
    if not hr_user:
        hr_user = UserDB(
            id=uuid4(),
            email="rrhh@recruitai.com",
            full_name="HR Usuario",
            role="recruiter",
            is_active=True,
            hashed_password=get_password_hash(recruiter_password),
        )
        db.add(hr_user)
        logger.info("Created default HR user: rrhh@recruitai.com")

    await db.commit()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Dependency to get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = decode_token(token)
    if token_data is None:
        raise credentials_exception

    # Look up by UUID (sub claim), not by email. Emails can be re-assigned
    # to a new user (delete + re-create) and an old token would silently
    # resurrect the previous user's privileges.
    try:
        user_uuid = UUID(token_data.user_id)
    except (ValueError, TypeError):
        raise credentials_exception
    user = await get_user_by_id(db, user_uuid)
    if user is None:
        raise credentials_exception
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Dependency to get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )
    return current_user


def get_current_admin_user(
    current_user: UserResponse = Depends(get_current_active_user),
) -> UserResponse:
    """Dependency: require admin role. 403 otherwise."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de administrador"
        )
    return current_user


# ============ Endpoints ============

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limit("5/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new recruiter — ADMIN ONLY.

    Closed by design: there is no public sign-up. The system is operated by
    a small set of HR analysts whose accounts are provisioned by the owner.
    Self-registration would let anyone on the internet read every CV in the
    database. The route is kept here (instead of removed) only to keep older
    admin-created scripts working — it requires the same admin token as
    /api/auth/users.
    """
    if await get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )

    user = UserDB(
        id=uuid4(),
        email=user_data.email,
        full_name=user_data.full_name,
        role="recruiter",
        is_active=True,
        hashed_password=get_password_hash(user_data.password),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"Admin {current_user.email} registered new user: {user.email}")

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/login", response_model=Token)
@limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    audit: AuditLogger = Depends(get_audit_logger),
):
    """
    Login and get access token.
    Uses OAuth2 password flow (username = email).

    LPDP: registra cada intento de login (exitoso y fallido) para detectar
    accesos no autorizados y reconstruir quién accedió al sistema cuándo.
    """
    # Ensure default users exist on first login attempt
    await ensure_default_users(db)

    user = await authenticate_user(db, form_data.username, form_data.password)
    client_ip = request.client.host if request.client else None

    if not user:
        # Login fallido — audit con email intentado pero sin user_id real.
        await audit.log_access(
            user_id="anonymous",
            action="login_failed",
            resource_type="user",
            resource_id=form_data.username[:80],  # email intentado (acotado)
            ip_address=client_ip,
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        await audit.log_access(
            user_id=str(user.id),
            action="login_blocked",
            resource_type="user",
            resource_id=str(user.id),
            ip_address=client_ip,
            details={"reason": "user_inactive"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    logger.info(f"User logged in: {user.email}")
    await audit.log_access(
        user_id=str(user.id),
        action="login_success",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=client_ip,
        details={"role": user.role},
    )

    return Token(access_token=access_token, token_type="bearer")


@router.post("/login/json", response_model=Token)
@limit("10/minute")
async def login_json(
    request: Request,
    credentials: LoginCredentials,
    db: AsyncSession = Depends(get_db),
    audit: AuditLogger = Depends(get_audit_logger),
):
    """
    Login with JSON body (alternative to form).

    LPDP: misma auditoría que ``/login`` — este es el endpoint que usa el
    frontend, así que sin estos logs los accesos reales (y los intentos de
    fuerza bruta por esta ruta) eran invisibles para ``audit_logs``.
    """
    # Ensure default users exist
    await ensure_default_users(db)

    user = await authenticate_user(db, credentials.email, credentials.password)
    client_ip = request.client.host if request.client else None

    if not user:
        await audit.log_access(
            user_id="anonymous",
            action="login_failed",
            resource_type="user",
            resource_id=credentials.email[:80],
            ip_address=client_ip,
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    if not user.is_active:
        await audit.log_access(
            user_id=str(user.id),
            action="login_blocked",
            resource_type="user",
            resource_id=str(user.id),
            ip_address=client_ip,
            details={"reason": "user_inactive"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    await audit.log_access(
        user_id=str(user.id),
        action="login_success",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=client_ip,
        details={"role": user.role},
    )

    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_active_user)):
    """
    Get current user profile.
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    update_data: UpdateMeRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's own profile (full_name only — role/status are admin-only)."""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.full_name = update_data.full_name

    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/change-password")
@limit("5/minute")
async def change_password(
    request: Request,
    passwords: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Change current user's password. Rate-limited to thwart brute force."""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not verify_password(passwords.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta"
        )

    user.hashed_password = get_password_hash(passwords.new_password)
    await db.commit()

    return {"message": "Contraseña actualizada correctamente"}


# ============ Admin Endpoints (IT Admin Only) ============

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users (Admin only)."""
    result = await db.execute(select(UserDB))
    users = result.scalars().all()
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    role: str = "recruiter",
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (Admin only)."""
    if await get_user_by_email(db, user_data.email):
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    user = UserDB(
        id=uuid4(),
        email=user_data.email,
        full_name=user_data.full_name,
        role=role,
        is_active=True,
        hashed_password=get_password_hash(user_data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"Admin created user: {user.email} with role {role}")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user (Admin only)."""
    user = await get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if user.email == current_user.email:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    
    await db.delete(user)
    await db.commit()
    
    logger.info(f"Admin deleted user: {user.email}")


@router.put("/users/{user_id}/password")
async def reset_user_password(
    user_id: UUID,
    password_data: AdminResetPasswordRequest,
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password (Admin only)."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()

    logger.info(f"Admin reset password for: {user.email}")
    return {"message": "Contraseña restablecida"}


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    role_data: AdminUpdateRoleRequest,
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's role (Admin only)."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.email == current_user.email and role_data.role != "admin":
        raise HTTPException(status_code=400, detail="No puedes quitarte el rol de admin")

    user.role = role_data.role
    await db.commit()

    logger.info(f"Admin updated role for {user.email} to {role_data.role}")
    return {"message": f"Rol actualizado a {role_data.role}"}


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    status_data: AdminUpdateStatusRequest,
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Activate or deactivate a user (Admin only)."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.email == current_user.email:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta")

    user.is_active = status_data.is_active
    await db.commit()

    status_msg = "activado" if status_data.is_active else "desactivado"
    logger.info(f"Admin {status_msg} user: {user.email}")
    
    return {"message": f"Usuario {status_msg}"}
