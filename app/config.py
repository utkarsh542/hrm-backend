"""Application configuration and settings."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    APP_NAME: str = "HRMS - HR Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./hrms.db"
    
    # JWT Auth
    SECRET_KEY: str = "hrms-super-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # File Upload
    UPLOAD_DIR: str = "uploads"
    GENERATED_DIR: str = "generated"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    
    # Company defaults
    COMPANY_NAME: str = "TechCorp Solutions Pvt. Ltd."
    COMPANY_ADDRESS: str = "123 Tech Park, Bangalore, Karnataka 560001"
    COMPANY_EMAIL: str = "hr@techcorp.com"
    COMPANY_PHONE: str = "+91-80-12345678"
    CURRENCY: str = "INR"
    CURRENCY_SYMBOL: str = "₹"
    
    class Config:
        env_file = ".env"


settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.GENERATED_DIR, exist_ok=True)
