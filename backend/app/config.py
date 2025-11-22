from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@db:5432/app"
    mistral_api_key: str
    openrouter_api_key: str | None = None
    anthropic_api_key: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra env variables not defined in Settings


settings = Settings()
