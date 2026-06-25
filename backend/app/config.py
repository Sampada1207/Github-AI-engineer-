import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App General Settings
    APP_NAME: str = "GitHub AI Engineer API"
    DEBUG: bool = True
    API_V1_STR: str = "/api"

    # Database Configuration (defaults to local SQLite, easily switches to PostgreSQL)
    DATABASE_URL: str = "sqlite:///./github_ai_engineer.db"

    # JWT Settings
    JWT_SECRET: str = "supersecretkeychangeinproduction1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

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

    # Local storage for cloned git repos
    CLONED_REPOS_DIR: str = "./cloned_repos"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Ensure directories exist
os.makedirs(settings.CLONED_REPOS_DIR, exist_ok=True)
if settings.QDRANT_PATH:
    os.makedirs(settings.QDRANT_PATH, exist_ok=True)
