from pydantic_settings import BaseSettings, SettingsConfigDict


class HFConfig(BaseSettings):
    HF_TOKEN: str = ""
    HF_HOME: str = "/workspace/.cache/huggingface"
    HF_HUB_ENABLE_HF_TRANSFER: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


hf_config = HFConfig()
