"""Application configuration and settings."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    APP_NAME: str = "HRMS - AI-Powered HR Management System"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./hrm.db"
    
    # JWT Auth
    SECRET_KEY: str = "hrms-super-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # File Upload
    UPLOAD_DIR: str = "uploads"
    GENERATED_DIR: str = "generated"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    
    # AI — Google Gemini (free tier)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    
    # AI — OpenRouter Free Tier
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openrouter/free"
    
    # SMTP Email Settings
    SMTP_SERVER: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@techcorp.com"

    
    # Company defaults
    COMPANY_NAME: str = "TechCorp Solutions Pvt. Ltd."
    COMPANY_ADDRESS: str = "123 Tech Park, Bangalore, Karnataka 560001"
    COMPANY_EMAIL: str = "hr@techcorp.com"
    COMPANY_PHONE: str = "+91-80-12345678"
    CURRENCY: str = "INR"
    CURRENCY_SYMBOL: str = "₹"
    
    # Geofence settings (TechCorp office center: Bangalore)
    ORG_LATITUDE: float = 12.9716
    ORG_LONGITUDE: float = 77.5946
    GEOFENCE_RADIUS_METERS: float = 100.0
    
    class Config:
        env_file = ".env"


settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.GENERATED_DIR, exist_ok=True)
os.makedirs(os.path.join(settings.UPLOAD_DIR, "documents"), exist_ok=True)
os.makedirs(os.path.join(settings.UPLOAD_DIR, "receipts"), exist_ok=True)
os.makedirs(os.path.join(settings.UPLOAD_DIR, "resumes"), exist_ok=True)
