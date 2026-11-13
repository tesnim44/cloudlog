
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    app_name: str = "CloudLog API"

    redis_url: str = "redis://localhost:6379/0"

    redis_queue: str = "cloudlog:logs"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
