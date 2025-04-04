import logging
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)
class Settings(BaseSettings):
    TELETHON_ID: str = Field(..., env='TELETHON_ID')
    TELETHON_HASH: str = Field(..., env='TELETHON_HASH')
    SQL_URL: str = Field(..., env='SQLALCHEMY_DATABASE_URL')

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


try:
    settings = Settings()
except ValidationError as e:
    logger.error(f"Configuration error: {e}")
    raise e