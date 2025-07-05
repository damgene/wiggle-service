"""
Configuration management for Wiggle Service.

Enhanced configuration with environment variable support and validation.
"""

import os
from typing import List, Optional, Any
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """MongoDB database configuration"""
    
    # MongoDB connection
    mongodb_url: str = Field(
        default=os.getenv("DATABASE_URL", "mongodb://localhost:27017"),
        description="MongoDB connection URL"
    )
    database_name: str = Field(
        default="wiggle",
        description="Database name"
    )
    
    # Connection pool settings
    min_pool_size: int = Field(default=10, ge=1)
    max_pool_size: int = Field(default=100, ge=1)
    
    # Timeout settings (milliseconds)
    connection_timeout_ms: int = Field(default=30000, ge=1000)
    server_selection_timeout_ms: int = Field(default=30000, ge=1000)
    
    class Config:
        env_prefix = "WIGGLE_DB_"


class RedisConfig(BaseSettings):
    """Redis configuration for caching and background tasks"""
    
    redis_url: str = Field(
        default=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        description="Redis connection URL"
    )
    
    # Cache settings
    cache_ttl_seconds: int = Field(default=300, ge=1)  # 5 minutes
    max_connections: int = Field(default=20, ge=1)
    
    class Config:
        env_prefix = "WIGGLE_REDIS_"


class APIConfig(BaseSettings):
    """API server configuration"""
    
    # Server settings
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    
    # API settings
    api_title: str = Field(default="Wiggle Service API")
    api_version: str = Field(default="0.1.0")
    api_description: str = Field(
        default="Core API and database service for Wiggle multi-exchange arbitrage system"
    )
    
    # Security
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT token generation"
    )
    access_token_expire_minutes: int = Field(default=30, ge=1)
    
    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins"
    )
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, ge=1)
    
    class Config:
        env_prefix = "WIGGLE_API_"


class MonitoringConfig(BaseSettings):
    """Monitoring and logging configuration"""
    
    # Logging
    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO"))
    log_format: str = Field(default="json")
    
    # Metrics
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=9090, ge=1, le=65535)
    
    # Health checks
    health_check_interval_seconds: int = Field(default=30, ge=1)
    
    # OpenTelemetry
    enable_tracing: bool = Field(default=False)
    jaeger_endpoint: Optional[str] = Field(default=None)
    
    class Config:
        env_prefix = "WIGGLE_MONITORING_"


class ExchangeConfig(BaseSettings):
    """Exchange API configuration"""
    
    # Rate limits (requests per minute)
    coingecko_rate_limit: int = Field(default=50, ge=1)
    binance_rate_limit: int = Field(default=1200, ge=1)
    coinbase_rate_limit: int = Field(default=300, ge=1)
    
    # Timeouts (seconds)
    api_timeout_seconds: int = Field(default=30, ge=1)
    
    # Retry settings
    max_retries: int = Field(default=3, ge=0)
    retry_delay_seconds: float = Field(default=1.0, ge=0.1)
    
    # Data validation
    max_price_deviation_percent: float = Field(default=50.0, ge=1.0)
    
    class Config:
        env_prefix = "WIGGLE_EXCHANGE_"


class OpportunityConfig(BaseSettings):
    """Opportunity analysis configuration"""
    
    # Profitability thresholds
    minimum_return_percent: float = Field(default=6.0, ge=0.1)
    historical_threshold_percent: float = Field(default=1.5, ge=0.1)
    
    # Cost estimates from EventScanner learnings
    default_gas_cost_usd: float = Field(default=35.0, ge=0.1)
    default_trading_fee_percent: float = Field(default=0.6, ge=0.0)
    
    # Analysis settings
    max_opportunities_per_token: int = Field(default=100, ge=1)
    opportunity_ttl_hours: int = Field(default=24, ge=1)
    
    # Priority scoring
    high_priority_return_threshold: float = Field(default=10.0, ge=1.0)
    medium_priority_return_threshold: float = Field(default=5.0, ge=1.0)
    
    class Config:
        env_prefix = "WIGGLE_OPPORTUNITY_"


class Settings(BaseSettings):
    """Main application settings"""
    
    # Environment
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    
    # Sub-configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    opportunity: OpportunityConfig = Field(default_factory=OpportunityConfig)
    
    @validator("environment")
    def validate_environment(cls, v):
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"
    
    class Config:
        env_prefix = "WIGGLE_"
        case_sensitive = False
        
        # Load from .env file if present
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance"""
    return settings


def reload_settings() -> Settings:
    """Reload settings from environment (useful for testing)"""
    global settings
    settings = Settings()
    return settings