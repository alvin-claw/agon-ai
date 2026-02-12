from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env from project root (one level above backend/)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = "http://localhost:54321"
    supabase_anon_key: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:54322/postgres"

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-haiku-4-5-20251001"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""

    # JWT
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Debate
    default_turn_timeout: int = 120
    default_turn_cooldown: int = 10
    default_max_turns: int = 10
    default_token_limit: int = 500

    model_config = {"env_file": str(_ENV_FILE), "extra": "ignore"}


settings = Settings()
