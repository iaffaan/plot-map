from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Uncharted Plot-Map Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # API Keys
    NVIDIA_API_KEY: str | None = Field(default=None, validation_alias=AliasChoices("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY"))
    GEMINI_API_KEY: str | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"))
    
    # Application Config
    ENVIRONMENT: str = "development"
    BACKEND_CORS_ORIGINS: list[str] = ["*","http://localhost:5173","https://plot-map-rho.vercel.app/"]
    
    # Solver Config
    SOLVER_TIMEOUT_SEC: int = 8

    # LLM Config (NVIDIA NIM / OpenAI-compatible)
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    NVIDIA_TIMEOUT_SEC: float = 60.0
    GEMINI_TIMEOUT_MS: int = 15_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
settings = Settings()
