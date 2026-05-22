from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    target_cik: str = Field(default="0000000000", alias="FOLLOWGOD_TARGET_CIK")
    target_name: str = Field(default="Situational Awareness LP", alias="FOLLOWGOD_TARGET_NAME")
    sec_user_agent: str = Field(
        default="FollowGod/0.1 your-email@example.com",
        alias="FOLLOWGOD_SEC_USER_AGENT",
    )
    database_path: Path = Field(default=Path("followgod.sqlite3"), alias="FOLLOWGOD_DATABASE_PATH")
    telegram_bot_token: str | None = Field(default=None, alias="FOLLOWGOD_TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="FOLLOWGOD_TELEGRAM_CHAT_ID")

    @property
    def normalized_cik(self) -> str:
        digits = "".join(ch for ch in self.target_cik if ch.isdigit())
        return digits.zfill(10)


@lru_cache
def get_settings() -> Settings:
    return Settings()
