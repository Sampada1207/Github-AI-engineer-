import os
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App General Settings
    APP_NAME: str = "GitHub AI Engineer API"
    DEBUG: bool = True
    API_V1_STR: str = "/api"

    # Database Configuration (defaults to local SQLite, easily switches to PostgreSQL)
    DATABASE_URL: str = "sqlite:///./github_ai_engineer.db"

    # JWT Settings — set JWT_SECRET in the environment for any non-debug deployment
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Comma-separated browser origins. Development defaults to the Next.js dev server.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Qdrant Vector DB Configuration
    QDRANT_PATH: Optional[str] = "./qdrant_data"  # local storage path
    QDRANT_HOST: Optional[str] = None
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "code_intelligence"

    # AI Configurations
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"

    # GitHub API Configuration
    GITHUB_TOKEN: Optional[str] = None

    # Canonical on-disk location for temporary clones
    CLONED_REPOS_DIR: str = "./cloned_repos"

    # Ingestion safety limits
    MAX_FILE_SIZE_BYTES: int = 2 * 1024 * 1024
    MAX_FILES_PER_REPO: int = 5000

    class Config:
        env_file = ".env"
        case_sensitive = True

    def cors_origin_list(self) -> List[str]:
        origins = [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]
        return origins or ["http://localhost:3000"]


settings = Settings()

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _resolve_dir(path: Optional[str]) -> Optional[str]:
    if not path:
        return path
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(_BACKEND_DIR, path))

settings.CLONED_REPOS_DIR = _resolve_dir(settings.CLONED_REPOS_DIR) or settings.CLONED_REPOS_DIR
if settings.QDRANT_PATH:
    settings.QDRANT_PATH = _resolve_dir(settings.QDRANT_PATH)

if settings.DATABASE_URL.startswith("sqlite:///./"):
    rel = settings.DATABASE_URL.replace("sqlite:///./", "", 1)
    settings.DATABASE_URL = "sqlite:///" + os.path.join(_BACKEND_DIR, rel)

_DEV_JWT_FALLBACK = "dev-only-insecure-jwt-secret-change-me-32b"

if not settings.JWT_SECRET:
    if settings.DEBUG:
        settings.JWT_SECRET = _DEV_JWT_FALLBACK
        print("WARNING: JWT_SECRET is unset. Using an insecure development fallback. Set JWT_SECRET before production.")
    else:
        raise ValueError("JWT_SECRET must be set when DEBUG is False.")
elif settings.JWT_SECRET == "supersecretkeychangeinproduction1234567890":
    if settings.DEBUG:
        print("WARNING: Default JWT_SECRET is in use. Set JWT_SECRET in the environment.")
    else:
        raise ValueError("Default JWT_SECRET is not allowed when DEBUG is False.")

# Ensure directories exist
os.makedirs(settings.CLONED_REPOS_DIR, exist_ok=True)
if settings.QDRANT_PATH:
    os.makedirs(settings.QDRANT_PATH, exist_ok=True)
