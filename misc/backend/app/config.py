"""
Configuration settings for the Nu Choate League API
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # MongoDB Configuration
    MONGODB_URI: str
    DATABASE_NAME: str = "nu_choate_league"
    
    # Sleeper API Configuration
    SLEEPER_LEAGUE_ID: str
    
    # Security
    JWT_SECRET: str
    
    # Environment
    API_ENV: str = "development"
    
    # Server
    PORT: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
