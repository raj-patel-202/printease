from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str

    razorpay_api_key: str
    razorpay_api_secret: SecretStr
    razorpay_webhook_secret: SecretStr
    currency: str = "INR"
    razorpay_timeout_seconds: int = 30
    web3forms_access_key: str

    # Printer agent (printer_pc) auth + timing. No inbound connection to the printer PC is needed.
    agent_token: SecretStr
    agent_online_seconds: int = 20          # agent counts as "online" if it polled this recently
    print_job_timeout_minutes: int = 30     # a job stuck in "printing" longer than this is marked failed
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    max_file_size_mb: int = 20

    cookie_name: str = "access_token"
    cookie_secure: bool

    admin_cookie_name: str = "admin_access_token"

    cost_per_page_bw: int = 2
    cost_per_page_co: int = 5
    double_sided_discount_pct: int = 20

settings = Settings()
