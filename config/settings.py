from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    anthropic_api_key: str
    supabase_url: str
    supabase_key: str
    upstash_redis_rest_url: Optional[str] = None
    upstash_redis_rest_token: Optional[str] = None
    telegram_api_id: Optional[str] = None
    telegram_api_hash: Optional[str] = None
    telegram_phone: Optional[str] = None
    fb_cookie: Optional[str] = None
    app_env: str = "production"
    max_leads_per_run: int = 20
    claude_model: str = "claude-3-5-haiku-20241022"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
