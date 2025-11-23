from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/postgres"
    mistral_api_key: str
    openrouter_api_key: str | None = None
    anthropic_api_key: str | None = None
    websocket_replay_speed: float = 4.0

    # Fraud Detection Agent limits
    fraud_detection_max_iterations: int = 80
    ranking_max_iterations: int = 10  # Ranking should be quick - max 3 tool calls
    fraud_detection_max_execution_time: int = 300  # seconds (5 minutes)

    # Workflow graph recursion limit (for parallel task processing)
    workflow_recursion_limit: int = 200  # Increased to handle parallel investigations

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra env variables not defined in Settings


settings = Settings()
