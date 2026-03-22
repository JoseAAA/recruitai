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
from pydantic import BaseModel, EmailStr
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
from app.db.models import UserDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ============ Request/Response Schemas ============

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


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

    if admin_password == "change-me-on-first-run":
        logger.warning(
            "⚠️  ADMIN_INITIAL_PASSWORD uses default value — set a strong password in your .env file before exposing to the internet!"
        )
    if recruiter_password == "change-me-on-first-run":
        logger.warning(
            "⚠️  RECRUITER_INITIAL_PASSWORD uses default value — set a strong password in your .env file before exposing to the internet!"
        )

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
    
    user = await get_user_by_email(db, token_data.email)
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


# ============ Endpoints ============

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.
    """
    # Check if user exists
    if await get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # Create new user
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
    
    logger.info(f"New user registered: {user.email}")
    
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
    db: AsyncSession = Depends(get_db)
):
    """
    Login and get access token.
    Uses OAuth2 password flow (username = email).
    """
    # Ensure default users exist on first login attempt
    await ensure_default_users(db)
    
    user = await authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    
    logger.info(f"User logged in: {user.email}")
    
    return Token(access_token=access_token, token_type="bearer")


@router.post("/login/json", response_model=Token)
@limit("10/minute")
async def login_json(request: Request, credentials: LoginCredentials, db: AsyncSession = Depends(get_db)):
    """
    Login with JSON body (alternative to form).
    """
    # Ensure default users exist
    await ensure_default_users(db)
    
    user = await authenticate_user(db, credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
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
    update_data: dict,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user profile.
    """
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if "full_name" in update_data:
        user.full_name = update_data["full_name"]
    
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
async def change_password(
    passwords: dict,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change current user's password.
    """
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    current_password = passwords.get("current_password", "")
    new_password = passwords.get("new_password", "")
    
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta"
        )
    
    user.hashed_password = get_password_hash(new_password)
    await db.commit()
    
    return {"message": "Contraseña actualizada correctamente"}


def get_current_admin_user(
    current_user: UserResponse = Depends(get_current_active_user),
) -> UserResponse:
    """Dependency to get current admin user."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de administrador"
        )
    return current_user


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
    password_data: dict,
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password (Admin only)."""
    user = await get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    new_password = password_data.get("new_password")
    if not new_password:
        raise HTTPException(status_code=400, detail="Se requiere new_password")
    
    user.hashed_password = get_password_hash(new_password)
    await db.commit()
    
    logger.info(f"Admin reset password for: {user.email}")
    
    return {"message": "Contraseña restablecida"}


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    role_data: dict,
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's role (Admin only)."""
    user = await get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    new_role = role_data.get("role")
    if new_role not in ["admin", "recruiter"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Use 'admin' o 'recruiter'")
    
    if user.email == current_user.email and new_role != "admin":
        raise HTTPException(status_code=400, detail="No puedes quitarte el rol de admin")
    
    user.role = new_role
    await db.commit()
    
    logger.info(f"Admin updated role for {user.email} to {new_role}")
    
    return {"message": f"Rol actualizado a {new_role}"}


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    status_data: dict,
    current_user: UserResponse = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Activate or deactivate a user (Admin only)."""
    user = await get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if user.email == current_user.email:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta")
    
    is_active = status_data.get("is_active", True)
    user.is_active = is_active
    await db.commit()
    
    status_msg = "activado" if is_active else "desactivado"
    logger.info(f"Admin {status_msg} user: {user.email}")
    
    return {"message": f"Usuario {status_msg}"}
