"""
Authentication API Routes
Login, register, and user management endpoints.
"""
import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from app.core.security import (
    Token,
    TokenData,
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ============ Request/Response Schemas ============

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool


class UserInDB(UserResponse):
    hashed_password: str


# ============ In-memory user storage (replace with DB) ============

_users_store: dict[str, UserInDB] = {}

# Create a default admin user
_default_admin = UserInDB(
    id=uuid4(),
    email="admin@recruitai.com",
    full_name="Admin User",
    role="admin",
    is_active=True,
    hashed_password=get_password_hash("admin123"),
)
_users_store["admin@recruitai.com"] = _default_admin


# ============ Helper Functions ============

def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Get user by email from storage."""
    return _users_store.get(email)


def authenticate_user(email: str, password: str) -> Optional[UserInDB]:
    """Authenticate user with email and password."""
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    """Dependency to get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = decode_token(token)
    if token_data is None:
        raise credentials_exception
    
    user = get_user_by_email(token_data.email)
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
async def register(user_data: UserCreate):
    """
    Register a new user.
    """
    # Check if user exists
    if get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # Create new user
    user = UserInDB(
        id=uuid4(),
        email=user_data.email,
        full_name=user_data.full_name,
        role="recruiter",
        is_active=True,
        hashed_password=get_password_hash(user_data.password),
    )
    
    _users_store[user.email] = user
    
    logger.info(f"New user registered: {user.email}")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login and get access token.
    Uses OAuth2 password flow (username = email).
    """
    user = authenticate_user(form_data.username, form_data.password)
    
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
async def login_json(credentials: dict):
    """
    Login with JSON body (alternative to form).
    """
    email = credentials.get("email", "")
    password = credentials.get("password", "")
    
    user = authenticate_user(email, password)
    
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
):
    """
    Update current user profile.
    """
    user = _users_store.get(current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if "full_name" in update_data:
        user.full_name = update_data["full_name"]
    
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
):
    """
    Change current user's password.
    """
    user = _users_store.get(current_user.email)
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
    
    return {"message": "Contraseña actualizada correctamente"}
