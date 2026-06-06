from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "DK Photo"
    data_dir: Path = Path(os.getenv("DK_PHOTO_DATA_DIR", "./data"))
    secret_key: str = os.getenv("DK_PHOTO_SECRET_KEY", "dev-only-change-me")
    access_token_minutes: int = int(os.getenv("DK_PHOTO_ACCESS_TOKEN_MINUTES", "10080"))
    admin_name: str = os.getenv("DK_PHOTO_ADMIN_NAME", "Administrator")
    admin_email: str = os.getenv("DK_PHOTO_ADMIN_EMAIL", "admin@example.com")
    admin_password: str = os.getenv("DK_PHOTO_ADMIN_PASSWORD", "change-me-now")
    default_library_path: str = os.getenv("DK_PHOTO_DEFAULT_LIBRARY_PATH", "")
    default_library_name: str = os.getenv("DK_PHOTO_DEFAULT_LIBRARY_NAME", "Family Photos")
    cors_origins: list[str] = None  # type: ignore[assignment]
    watch_enabled: bool = _env_bool("DK_PHOTO_WATCH_ENABLED", False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "cors_origins",
            _env_list("DK_PHOTO_CORS_ORIGINS", ["http://localhost:5173", "http://localhost:8080"]),
        )
        object.__setattr__(self, "data_dir", self.data_dir.resolve())

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'dk_photo.sqlite3'}"

    @property
    def thumbnail_dir(self) -> Path:
        return self.data_dir / "thumbnails"


settings = Settings()
