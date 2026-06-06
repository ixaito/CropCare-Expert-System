import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _bool(value: str, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Agricultural Crop Disease Diagnostic System")
    secret_key: str = os.getenv("APP_SECRET_KEY", "dev-only-change-this-secret")
    app_base_url: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./agri_diagnosis.db")

    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587") or 587)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "no-reply@cropdiagnosis.local")
    smtp_tls: bool = _bool(os.getenv("SMTP_TLS", "true"), True)


settings = Settings()
