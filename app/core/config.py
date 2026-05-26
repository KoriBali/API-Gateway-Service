from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "API Gateway"
    app_port: int = 8000

    calc_service_url: str
    calc_service_key: str

    DATABASE_URL: str
    DEBUG: str

    INTERNAL_CLEANUP_TOKEN:str

    class Config:
        env_file = ".env"

settings = Settings()