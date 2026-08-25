import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from core.config import load_application_env

load_application_env()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set. Set it in .env before starting the API.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_ISSUER = os.getenv("JWT_ISSUER", "srtime-api")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "srtime-web")
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres")
    if not password.isascii() or not password.isalnum():
        raise ValueError("La contraseña solo puede contener letras y números")
    if not any(character.isalpha() for character in password) or not any(character.isdigit() for character in password):
        raise ValueError("La contraseña debe incluir al menos una letra y un número")
