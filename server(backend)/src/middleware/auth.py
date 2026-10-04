"""JWT authentication middleware / FastAPI dependency."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.db.database import get_db
from src.db.models import User

_settings = get_settings()
_bearer = HTTPBearer(auto_error=True)


def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency: extracts the JWT from Authorization: Bearer <token>,
    verifies it server-side, and returns the User from the database.
    Raises 401 if invalid.
    """
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
        )

    email: str | None = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
        )

    user = db.query(User).filter(User.email == email, User.active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account deactivated.",
        )
    return user


def require_role(*roles: str):
    """
    Dependency factory: requires one of the listed roles.
    Usage: Depends(require_role('admin', 'ops'))
    """
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted. Required: {list(roles)}",
            )
        return current_user
    return checker
