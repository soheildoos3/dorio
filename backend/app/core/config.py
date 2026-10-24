from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    DEBUG: bool = False
    MEDIA_DIR: Path = Path("storage/media")
    MAX_IMAGE_SIZE_MB: int = 10
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 480
    COOKIE_SECURE: bool = False
    CORS_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174"
    WARRANTY_BASE_URL: str = "http://127.0.0.1:5174/warranty"
    PANEL_BASE_URL: str = "http://127.0.0.1:5173"
    WARRANTY_TIMEZONE: str = "Asia/Tehran"
    WARRANTY_REFRESH_SECONDS: int = 3600
    REPORT_FONT_PATH: Path | None = None

    @model_validator(mode="after")
    def validate_security(self):
        if not self.DEBUG and (self.JWT_SECRET_KEY == "change-me-in-production" or len(self.JWT_SECRET_KEY) < 32):
            raise ValueError("JWT_SECRET_KEY must be a strong value of at least 32 characters outside DEBUG mode")
        if self.ACCESS_TOKEN_MINUTES < 5 or self.ACCESS_TOKEN_MINUTES > 1440:
            raise ValueError("ACCESS_TOKEN_MINUTES must be between 5 and 1440")
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
settings = Settings()
