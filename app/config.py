from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量或 .env 文件读取。"""

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/peakstate"
    DATABASE_URL_SYNC: str = "postgresql://postgres:password@localhost:5432/peakstate"

    APP_ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    MAX_RECENT_MEMORIES: int = 10
    DEFAULT_IMPORTANCE_SCORE: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
