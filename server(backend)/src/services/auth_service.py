"""Authentication service — password hashing and JWT token creation."""
from datetime import datetime, timedelta

from jose import jwt
import bcrypt
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.db.models import User

_settings = get_settings()
def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(user: User) -> str:
    """Create a signed JWT containing role and station access."""
    payload = {
        "sub": user.email,
        "name": user.name,
        "role": user.role,
        "stations": user.stations,
        "exp": datetime.utcnow() + timedelta(seconds=_settings.JWT_EXPIRES_IN),
    }
    return jwt.encode(payload, _settings.JWT_SECRET, algorithm="HS256")


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the User if credentials are valid, else None."""
    user = db.query(User).filter(User.email == email, User.active == True).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
