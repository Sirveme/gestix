from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from app.config import settings
import bcrypt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        plain_bytes = plain.encode('utf-8')[:72]
        hashed_bytes = hashed.encode('utf-8') if isinstance(hashed, str) else hashed
        result = bcrypt.checkpw(plain_bytes, hashed_bytes)
        print(f"[AUTH] verify_password result={result} hash_prefix={hashed[:20]}")
        return result
    except Exception as e:
        print(f"[AUTH] verify_password ERROR: {e}")
        return False


def crear_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
