from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables, never hard-coded secrets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VERITYGRAPH_",
        extra="ignore",
    )

    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    max_upload_bytes: int = 10 * 1024 * 1024

    wikipedia_provider: str = "live"
    wikipedia_endpoint: str = "https://en.wikipedia.org/w/api.php"
    wikipedia_language: str = "en"
    wikipedia_timeout_seconds: float = 12.0
    wikipedia_user_agent: str = (
        "VerityGraphAI/0.4 (+https://github.com/mohit231007/veritygraph-ai)"
    )

    web_provider: str = "live"
    web_timeout_seconds: float = 12.0
    web_max_content_bytes: int = 3 * 1024 * 1024
    web_max_redirects: int = 4
    web_user_agent: str = "VerityGraphAI/0.4 (+https://github.com/mohit231007/veritygraph-ai)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
