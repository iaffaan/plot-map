from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Uncharted Plot-Map Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # API Keys
    GEMINI_API_KEY: str | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"))
    
    # Application Config
    ENVIRONMENT: str = "development"
    BACKEND_CORS_ORIGINS: list[str] = ["*","http://localhost:5173","https://plot-map-rho.vercel.app/"]
    
    # Solver Config
    SOLVER_TIMEOUT_SEC: int = 8

    # Gemini HTTP request timeout, in milliseconds
    GEMINI_TIMEOUT_MS: int = 10_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
settings = Settings()
