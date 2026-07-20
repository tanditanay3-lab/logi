"""
Configuration for Saas-api.
"""

import os
from typing import List

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings."""
    
    # Environment
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    
    # Database
    SAAS_DATABASE_URL: str = Field(
        default="postgresql+asyncpg://neondb_owner:npg_3YDpWTUa2ifV@ep-bitter-block-az9ls0rp.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
        env="SAAS_DATABASE_URL"
    )
    
    # Neon Auth
    NEON_AUTH_URL: str = Field(
        default="https://auth.neon.tech",
        env="NEON_AUTH_URL"
    )
    NEON_AUTH_PROJECT_ID: str = Field(
        default="",
        env="NEON_AUTH_PROJECT_ID"
    )
    NEON_AUTH_API_KEY: str = Field(
        default="",
        env="NEON_AUTH_API_KEY"
    )
    
    # JWT
    JWT_SECRET_KEY: str = Field(
        default="change-me-in-production",
        env="JWT_SECRET_KEY"
    )
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRE_MINUTES: int = Field(default=60 * 24, env="JWT_EXPIRE_MINUTES")  # 24 hours
    
    # CORS
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        env="CORS_ORIGINS"
    )
    
    # Agent Platform
    AGENT_PLATFORM_URL: str = Field(
        default="http://localhost:8001",
        env="AGENT_PLATFORM_URL"
    )
    AGENT_PLATFORM_API_KEY: str = Field(
        default="",
        env="AGENT_PLATFORM_API_KEY"
    )
    
    # Server
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
