from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    token: str = None
    guild_id: Optional[int] = None
    debug: bool = False
    database_path: str = "data/bot.db"

    mod_role_id: int = None
    mod_log_channel_id: Optional[int] = None

    confession_channel_id: Optional[int] = None
    confession_rate_limit_seconds: Optional[int] = None


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
