"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import AuthStatus, LoginRequest, Token, UserCreate, UserOut
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    decode_access_token,
    ensure_admin_user,
    get_auth_status,
    get_user_by_username,
    get_any_user,
    DEFAULT_PASSWORD,
)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    token_query: str | None = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
):
    """Dependency: extract current user from JWT bearer token.

    Accepts token from either:
    - Authorization: Bearer <token> header (standard)
    - ?token=<token> query parameter (for EventSource/SSE which can't set headers)
    """
    from app.models.user import User

    resolved_token = token or token_query
    if not resolved_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(resolved_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    user = await get_user_by_username(db, username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


@router.get("/status", response_model=AuthStatus)
async def auth_status(db: AsyncSession = Depends(get_db)):
    """Check authentication status.
    Returns whether login is required and if a password has been set.
    """
    return await get_auth_status(db)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    existing = await get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    user = await create_user(db, body.username, body.password)
    return user


@router.post("/token", response_model=Token, include_in_schema=False)
async def login_for_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2-compatible login endpoint for Swagger UI.

    Accepts form-encoded data (username + password) as required by
    OAuth2 password flow. Maps to the existing password-only auth.
    The username field is ignored — only password is checked.
    """
    any_user = await get_any_user(db)

    if any_user is None:
        if form_data.password != DEFAULT_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password",
            )
        admin = await ensure_admin_user(db)
        token = create_access_token(data={"sub": admin.username})
        return Token(access_token=token)

    user = await authenticate_user(db, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )
    token = create_access_token(data={"sub": user.username})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with password only (9Router pattern).

    - If no users exist: auto-create 'admin' with the given password.
      Only succeeds if password matches the default '123456'.
    - If users exist: try authenticating as 'admin' with the given password.
    """
    any_user = await get_any_user(db)

    if any_user is None:
        # No users exist yet - auto-create admin
        if body.password != DEFAULT_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password",
            )
        # Create admin user with default password
        admin = await ensure_admin_user(db)
        token = create_access_token(data={"sub": admin.username})
        return Token(access_token=token)

    # Users exist - authenticate
    user = await authenticate_user(db, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )
    token = create_access_token(data={"sub": user.username})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user
