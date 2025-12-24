"""JWT authentication middleware for Supabase."""
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel

from ..config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()
admin_security = HTTPBearer()


class User(BaseModel):
    """Authenticated user from JWT."""

    user_id: str
    email: Optional[str] = None
    role: str = "authenticated"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Verify Supabase JWT and extract user information.

    Args:
        credentials: HTTP Bearer token from request header

    Returns:
        User: User object with user_id and email

    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials

    try:
        # Decode and verify the JWT using Supabase JWT secret
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )

        # Extract user information from the token
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )

        email = payload.get("email")
        role = payload.get("role", "authenticated")

        return User(user_id=user_id, email=email, role=role)

    except JWTError as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(user: User = Depends(get_current_user)) -> User:
    """
    Require admin privileges for endpoint access.

    Checks if the authenticated user's ID is in the ADMIN_USER_IDS allowlist.

    Args:
        user: Authenticated user from JWT (via get_current_user dependency)

    Returns:
        User: The authenticated admin user

    Raises:
        HTTPException: 403 Forbidden if user is not an admin
    """
    admin_ids = settings.admin_user_ids_list

    if not admin_ids:
        logger.warning("ADMIN_USER_IDS not configured - no admin access allowed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access not configured",
        )

    if user.user_id not in admin_ids:
        logger.warning(f"Non-admin user {user.user_id} attempted to access admin endpoint")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    logger.debug(f"Admin access granted to user {user.user_id}")
    return user
