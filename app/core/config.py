import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "kaapi-db"
    POSTGRES_DB: str = "kaapi"
    POSTGRES_ECHO: bool = False
    # Basic Configuration
    PROJECT_NAME: str = "KAAPI Backend"
    ENVIRONMENT: str = "development"
    
    # API Configuration
    API_PREFIX: str = "/api"  # Central prefix for all API routes
    API_V1_STR: str = "/api" 
    
    # Security
    SECRET_KEY: str = "CHANGE_ME"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10  # For tests, only 2 minutes
    REFRESH_TOKEN_EXPIRE_DAYS: int = 1  # For tests, only 1 day
    ALGORITHM: str = "HS256"
    
    # OAuth Providers
    OAUTH_PROVIDERS: dict = {
        "github": {
            "client_id": os.getenv("GITHUB_CLIENT_ID", "default_github_client_id"),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET", "default_github_client_secret"),
        },
        "google": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", "xxxxxxx"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "xxxxxx"),
        },
        "facebook": {
            "client_id": os.getenv("FACEBOOK_CLIENT_ID", "default_facebook_client_id"),
            "client_secret": os.getenv("FACEBOOK_CLIENT_SECRET", "default_facebook_client_secret"),
        },
    }
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://sevoil.kortexai.dev",      # <--- TON FRONT DE PROD
        "https://petro-api.kortexai.dev",   # TON API (parfois utile pour Swagger)
        "*"                                 # <--- AJOUTE ÇA POUR LE MEETING (SÉCURITÉ TOTALE)
    ]
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]
    
    # Celery
    CELERY_BROKER_REDIS_DATABASE: int = 0
    CELERY_BACKEND_REDIS_DATABASE: int = 1
    
    # Messaging
    GMAIL_USERNAME: Optional[str] = None
    GMAIL_PASSWORD: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None
    INFOBIP_API_KEY: Optional[str] = None
    INFOBIP_BASE_URL: Optional[str] = None
    INFOBIP_FROM_NUMBER: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None
    ONESIGNAL_APP_ID: Optional[str] = None
    ONESIGNAL_REST_API_KEY: Optional[str] = None
    
    # RabbitMQ
    RABBITMQ_USERNAME: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    

    # Env Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DATABASE: int = 0


    DEEPSEEK_API_KEY: str = ""
    # Configuration optionnelle pour LangSmith
    LANGSMITH_TRACING_V2: Optional[str] = "true"
    LANGSMITH_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = ""

    # Logging
    LOKI_URL: str = "http://loki:3100"
    
    @property
    def CELERY_BROKER_URL(self) -> str:
        password = f":{self.REDIS_PASSWORD}" if self.REDIS_PASSWORD else ""
        return f"redis://{password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_BROKER_REDIS_DATABASE}"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        password = f":{self.REDIS_PASSWORD}" if self.REDIS_PASSWORD else ""
        return f"redis://{password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_BACKEND_REDIS_DATABASE}"
    
    @property
    def DB_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:5432/{self.POSTGRES_DB}"
    
    @property
    def ASYNC_DB_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:5432/{self.POSTGRES_DB}"
    
    # Configuration for environment variable analysis
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
