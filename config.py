from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Zomato Food Ordering"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True
    
    # Zomato MCP
    MCP_SERVER_URL: str = "https://mcp-server.zomato.com/mcp"
    MCP_CLIENT_ID: str = "your-client-id"  # You'll get this from Zomato
    MCP_CLIENT_SECRET: str = "your-client-secret"  # You'll get this from Zomato
    MCP_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    
    # Session
    SESSION_SECRET_KEY: str = "your-session-secret-change-this"
    SESSION_MAX_AGE: int = 3600  # 1 hour
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    STATIC_DIR: Path = BASE_DIR / "static"
    
    # Google Gemini (for NLP)
    GEMINI_API_KEY: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()
