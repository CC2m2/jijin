from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fund Valuation MVP"
    api_v1_prefix: str = "/api/v1"
    sqlite_db_path: Path = Path("./data/app.db")
    fund_data_timeout_seconds: float = 10.0
    cache_ttl_seconds: int = 180
    openclaw_token: str | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.sqlite_db_path.as_posix()}"


settings = Settings()
