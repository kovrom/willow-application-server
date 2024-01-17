from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    command_not_found: str = "Sorry, I can't find that command"
    openai_api_key: str = "undefined"
    openai_base_url: str = "https://api.endpoints.anyscale.com/v1"
    openai_model: str = "meta-llama/Llama-2-70b-chat-hf"
    openai_system_prompt: str = "Keep your answers as short as possible."
    openai_temperature: float = 0.1
    was_version: str = "unknown"


@lru_cache
def get_settings():
    return Settings()
