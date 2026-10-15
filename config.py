from pathlib import Path
import os
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    trusted_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    upload_dir: Path = Path(__file__).parent / "resource" / "uploads"
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: int = Field(default=10, ge=1)
    db_statement_timeout_ms: int = Field(default=15000, ge=1000)
    max_pdf_pages: int = Field(default=1000, ge=1)
    min_free_upload_mb: int = Field(default=1024, ge=0)

    razorpay_api_key: str
    razorpay_api_secret: SecretStr
    razorpay_webhook_secret: SecretStr
    currency: str = "INR"
    razorpay_timeout_seconds: int = Field(default=30, ge=1, le=120)
    web3forms_access_key: str

    # Printer agent (printer_pc) auth + timing. No inbound connection to the printer PC is needed.
    agent_token: SecretStr
    agent_online_seconds: int = Field(default=20, ge=1)
    print_job_timeout_minutes: int = Field(default=30, ge=1)
    secret_key: SecretStr
    algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)

    max_file_size_mb: int = Field(default=20, ge=1, le=100)

    cookie_name: str = "access_token"
    cookie_secure: bool

    admin_cookie_name: str = "admin_access_token"

    cost_per_page_bw: int = Field(default=2, ge=1)
    cost_per_page_co: int = Field(default=5, ge=1)
    double_sided_discount_pct: int = Field(default=20, ge=0, le=100)

    @model_validator(mode="after")
    def production_safety(self):
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        if self.environment == "production":
            if not self.cookie_secure:
                raise ValueError("Production requires COOKIE_SECURE=true")
            if not self.allowed_hosts or "*" in self.allowed_hosts:
                raise ValueError("Production requires explicit ALLOWED_HOSTS")
            if not self.trusted_origins or any(not origin.startswith("https://") for origin in self.trusted_origins):
                raise ValueError("Production requires HTTPS TRUSTED_ORIGINS")
            for secret in (self.secret_key, self.agent_token, self.razorpay_webhook_secret):
                value = secret.get_secret_value()
                if len(value) < 32 or value.startswith("your_"):
                    raise ValueError(
                        "Production secrets must contain at least 32 characters and cannot be placeholders"
                    )
        return self


# Test tools must never pick up a developer's payment keys from the local .env.
settings = Settings(_env_file=None if os.getenv("ENVIRONMENT") == "test" else ".env")
