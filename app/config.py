from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
import os

class Settings(BaseSettings):
    # Modo de despliegue
    MODO_DEPLOY: str = "cloud"          # "cloud" | "local"
    ENTORNO: str = "development"         # "development" | "production"

    # Base de datos
    DATABASE_URL: str = "postgresql+asyncpg://erp:erp@localhost:5432/erpro"
    DATABASE_URL_SYNC: str = "postgresql://erp:erp@localhost:5432/erpro"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def asegurar_asyncpg(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # Sistema
    SECRET_KEY: str = "cambiar-en-produccion-usar-secrets-token-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 8

    # Licencias (nube)
    LICENCIAS_API_URL: str = ""
    LICENCIAS_API_KEY: str = ""

    # App
    APP_NOMBRE: str = "erpPro"
    APP_VERSION: str = "0.1.0"

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
