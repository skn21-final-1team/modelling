from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./dev.db"

    PROJECT_NAME: str = "Modelling Service"
    DEBUG: bool = False

    HF_TOKEN: str = ""
    HF_HOME: str = "/workspace/.cache/huggingface"
    HF_HUB_ENABLE_HF_TRANSFER: bool = True

    VLLM_BASE_URL: str = "http://localhost:8000"

    MONITORING_LOG_DIR: str = "data/monitoring"
    RAW_DATA_DIR: str = "data/raw"
    PROCESSED_DATA_DIR: str = "data/processed"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
