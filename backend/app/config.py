from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://f2m_user:f2m_password@localhost:5432/farm2market"
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    platform_fee_percent: float = 8.0
    logistics_share_percent: float = 15.0

    class Config:
        env_file = ".env"


settings = Settings()