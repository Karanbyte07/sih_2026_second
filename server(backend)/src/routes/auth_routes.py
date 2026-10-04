"""Auth routes: /api/health and /api/login."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.services.auth_service import authenticate_user, create_access_token
from src.services.audit_service import log_action

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/health")
async def health():
    return {"ok": True, "simulated": True, "phase": 8}


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials (demo password: antarctic)",
        )

    token = create_access_token(user)
    log_action(db, "Logged in", user=user, entity_type="user", entity_id=str(user.id))

    return {
        "user": {
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "stations": user.stations,
        },
        "token": token,
    }
