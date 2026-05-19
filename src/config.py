from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # API Authentication
    API_KEY_SECRET: str = "super-secret-key-change-me-in-prod"

    # Database
    DATABASE_URL: str = "postgresql://memory_user:memory_password@localhost:5433/memory_layer"
    
    # AI Providers (openai, anthropic, local)
    EMBEDDING_PROVIDER: str = "local"
    LLM_PROVIDER: str = "local"

    # API Keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
