"""Authentication module."""
from .middleware import get_current_user, User

__all__ = ["get_current_user", "User"]
