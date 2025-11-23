from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/postgres"
    mistral_api_key: str
    openrouter_api_key: str | None = None
    anthropic_api_key: str | None = None
    websocket_replay_speed: float = 4.0

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra env variables not defined in Settings


settings = Settings()
