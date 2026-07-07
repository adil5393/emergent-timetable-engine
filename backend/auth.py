"""JWT auth + password hashing + role dependencies."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Iterable

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole


JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    token = request.cookies.get("access_token")
    if token:
        return token
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_roles(*roles: str):
    allowed = {r for r in roles}

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in allowed:
            raise HTTPException(status_code=403, detail=f"Requires one of roles: {sorted(allowed)}")
        return user

    return _dep


def require_editor(user: User = Depends(get_current_user)) -> User:
    """Admin or Planner can write; Viewer is read-only."""
    if user.role.value not in {"admin", "planner"}:
        raise HTTPException(status_code=403, detail="Read-only role")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def seed_default_users(db: Session) -> None:
    seeds: Iterable[tuple[str, str, str, UserRole]] = (
        (os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"], "Administrator", UserRole.admin),
        (os.environ.get("PLANNER_EMAIL", "planner@timetable.app"),
         os.environ.get("PLANNER_PASSWORD", "planner123"),
         "Planner", UserRole.planner),
        (os.environ.get("VIEWER_EMAIL", "viewer@timetable.app"),
         os.environ.get("VIEWER_PASSWORD", "viewer123"),
         "Viewer", UserRole.viewer),
    )
    for email, pw, name, role in seeds:
        existing = db.query(User).filter(User.email == email).first()
        if existing is None:
            db.add(User(email=email, password_hash=hash_password(pw), name=name, role=role))
        elif not verify_password(pw, existing.password_hash):
            existing.password_hash = hash_password(pw)
    db.commit()
