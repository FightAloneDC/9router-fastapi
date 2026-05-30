"""Authentication service: password hashing, JWT creation, user CRUD."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.models.settings import SettingsModel

# Backwards-compat alias — prefer settings.ADMIN_PASSWORD directly
DEFAULT_PASSWORD = settings.ADMIN_PASSWORD


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT. Returns payload dict or None on failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# --- DB operations ---


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Fetch a user by username."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_any_user(db: AsyncSession) -> User | None:
    """Fetch any user (for checking if users exist)."""
    result = await db.execute(select(User).limit(1))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, username: str, password: str) -> User:
    """Create a new user and persist to DB."""
    user = User(
        id=uuid.uuid4(),
        username=username,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def ensure_admin_user(db: AsyncSession) -> User:
    """Ensure admin user exists, create with default password if not.
    Returns the admin user."""
    admin = await get_user_by_username(db, "admin")
    if admin:
        return admin
    admin = await create_user(db, "admin", DEFAULT_PASSWORD)
    await db.commit()
    return admin


async def authenticate_user(db: AsyncSession, password: str, username: str = "admin") -> User | None:
    """Authenticate user credentials. Returns User on success, None on failure.
    When no username given, defaults to 'admin' user.
    """
    user = await get_user_by_username(db, username)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_auth_status(db: AsyncSession) -> dict:
    """Get auth status: requireLogin and hasPassword."""
    # Check if any user exists
    any_user = await get_any_user(db)
    has_password = any_user is not None

    # Check settings table for password field
    require_login = True  # default
    try:
        result = await db.execute(
            select(SettingsModel).where(SettingsModel.id == 1)
        )
        settings_row = result.scalar_one_or_none()
        if settings_row and settings_row.data:
            data = json.loads(settings_row.data)
            # If settings explicitly has a password-related config
            if "password" in data:
                require_login = True
    except Exception:
        pass

    return {
        "requireLogin": require_login,
        "hasPassword": has_password,
    }
