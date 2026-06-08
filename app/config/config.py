from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    ollama_url: str = "http://localhost:11434"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    rag_factsheet_limit: int = 5


settings = Settings()
