from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量或 .env 文件读取。"""

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/peakstate"
    DATABASE_URL_SYNC: str = "postgresql://postgres:password@localhost:5432/peakstate"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "peakstate_memory"

    # LLM
    LLM_PROVIDER: str = "anthropic"
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-5-20241022"

    APP_ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    MAX_RECENT_MEMORIES: int = 10
    DEFAULT_IMPORTANCE_SCORE: int = 5
    DAILY_SUMMARY_HOUR: int = 23
    WEEKLY_SUMMARY_DAY: int = 0  # 0 = Monday

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
