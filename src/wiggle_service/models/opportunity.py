"""
MongoDB document models for opportunities.

Enhanced from EventScanner with Beanie ODM and improved indexing.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from beanie import Document, Indexed
from pydantic import BaseModel, Field
from pymongo import IndexModel, ASCENDING, DESCENDING

from wiggle_common.models import (
    OpportunityClass,
    RiskLevel,
    AutomationFeasibility,
    ChainType,
    ExchangeType,
)


class TokenDocument(Document):
    """
    Token document for MongoDB storage.
    
    Enhanced from EventScanner with better indexing and validation.
    """
    
    # Core token data
    symbol: Indexed(str) = Field(description="Token symbol (e.g., ETH)")
    name: str = Field(description="Token name (e.g., Ethereum)")
    address: Optional[str] = Field(default=None, description="Contract address")
    chain: ChainType = Field(description="Blockchain network")
    
    # Additional token metadata
    decimals: Optional[int] = Field(default=18, ge=0, le=18)
    coingecko_id: Optional[str] = Field(default=None)
    coinmarketcap_id: Optional[str] = Field(default=None)
    
    # Tracking
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    notes: str = Field(default="")
    
    class Settings:
        name = "tokens"
        indexes = [
            IndexModel([("symbol", ASCENDING)]),
            IndexModel([("chain", ASCENDING)]),
            IndexModel([("symbol", ASCENDING), ("chain", ASCENDING)], unique=True),
            IndexModel([("is_active", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]


class ExchangeDocument(Document):
    """
    Exchange document for MongoDB storage.
    
    Enhanced from EventScanner with health tracking and rate limit monitoring.
    """
    
    # Core exchange data
    name: Indexed(str) = Field(description="Exchange name")
    exchange_type: ExchangeType = Field(description="CEX or DEX")
    
    # API configuration
    api_endpoint: Optional[str] = Field(default=None)
    rate_limit_per_minute: int = Field(default=60, ge=1)
    
    # Health tracking
    is_active: bool = Field(default=True)
    last_successful_request: Optional[datetime] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
    consecutive_errors: int = Field(default=0, ge=0)
    
    # Statistics
    total_requests: int = Field(default=0, ge=0)
    total_errors: int = Field(default=0, ge=0)
    average_response_time_ms: Optional[float] = Field(default=None, ge=0)
    
    # Supported features
    supports_historical_data: bool = Field(default=True)
    supports_websocket: bool = Field(default=False)
    supported_chains: List[ChainType] = Field(default_factory=list)
    
    # Tracking
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Settings:
        name = "exchanges"
        indexes = [
            IndexModel([("name", ASCENDING)], unique=True),
            IndexModel([("exchange_type", ASCENDING)]),
            IndexModel([("is_active", ASCENDING)]),
            IndexModel([("last_successful_request", DESCENDING)]),
        ]


class OpportunityDocument(Document):
    """
    Single opportunity document for MongoDB storage.
    
    Enhanced from EventScanner with cost tracking and execution metadata.
    """
    
    # Core opportunity classification
    opportunity_class: OpportunityClass
    
    # Financial metrics
    estimated_return_percent: float = Field(ge=0, description="Expected return percentage")
    capital_required_usd: float = Field(gt=0, description="Required capital in USD")
    net_return_percent: Optional[float] = Field(default=None, description="Return after costs")
    
    # Timing
    duration_hours: float = Field(gt=0, description="Expected duration in hours")
    data_timestamp: Indexed(datetime) = Field(default_factory=datetime.now)
    
    # Risk assessment
    exploited_by_big_bots: bool = Field(default=False)
    small_size_edge: bool = Field(default=True)
    risk_level: RiskLevel
    
    # Trading details
    source_exchanges: List[str] = Field(min_items=1, description="Exchanges involved")
    
    # Token information
    token_symbol: Optional[Indexed(str)] = None
    token_name: Optional[str] = None
    token_address: Optional[str] = None
    token_chain: Optional[ChainType] = None
    
    # Execution cost estimates (from EventScanner context)
    gas_cost_usd: float = Field(default=35.0, description="Estimated gas cost in USD")
    trading_fees_percent: float = Field(default=0.6, description="Combined trading fees")
    
    # Confidence and automation
    confidence_score: float = Field(ge=0, le=100, default=50, description="Confidence in opportunity")
    automation_feasibility: AutomationFeasibility = AutomationFeasibility.PARTIAL
    
    # Execution tracking
    is_executed: bool = Field(default=False)
    execution_timestamp: Optional[datetime] = Field(default=None)
    execution_result: Optional[Dict[str, Any]] = Field(default=None)
    
    # Metadata
    notes: str = Field(default="", description="Additional notes")
    instructions: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # Tracking
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = Field(default=None)
    
    class Settings:
        name = "opportunities"
        indexes = [
            IndexModel([("opportunity_class", ASCENDING)]),
            IndexModel([("token_symbol", ASCENDING)]),
            IndexModel([("data_timestamp", DESCENDING)]),
            IndexModel([("estimated_return_percent", DESCENDING)]),
            IndexModel([("risk_level", ASCENDING)]),
            IndexModel([("is_executed", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("expires_at", ASCENDING)]),
            # Compound indexes for common queries
            IndexModel([("token_symbol", ASCENDING), ("data_timestamp", DESCENDING)]),
            IndexModel([("opportunity_class", ASCENDING), ("estimated_return_percent", DESCENDING)]),
            IndexModel([("is_executed", ASCENDING), ("estimated_return_percent", DESCENDING)]),
        ]


class ExchangePairOpportunityEmbedded(BaseModel):
    """
    Embedded document for exchange pair opportunities.
    
    NEW for Wiggle - represents directional arbitrage between two exchanges.
    """
    
    date: datetime
    exchange_from: str = Field(description="Buy exchange")
    exchange_to: str = Field(description="Sell exchange")
    price_from: float = Field(gt=0, description="Buy price")
    price_to: float = Field(gt=0, description="Sell price")
    return_percent: float = Field(description="Gross return percentage")
    price_difference: float = Field(description="Absolute price difference")
    volume_from: float = Field(ge=0, default=0, description="24h volume on buy exchange")
    volume_to: float = Field(ge=0, default=0, description="24h volume on sell exchange")


class MultiExchangeOpportunityDocument(Document):
    """
    Multi-exchange opportunity document for MongoDB storage.
    
    NEW for Wiggle - aggregated opportunities across multiple exchange pairs.
    """
    
    # Token information
    symbol: Indexed(str)
    name: str
    contract_address: Optional[str] = None
    supported_exchanges: List[str] = Field(min_items=2)
    
    # Exchange pair opportunities (stored as embedded documents)
    exchange_pair_opportunities: Dict[str, List[ExchangePairOpportunityEmbedded]] = Field(
        description="Opportunities per exchange pair (e.g., 'binance→uniswap')"
    )
    
    # Best spreads per pair
    best_spreads_per_pair: Dict[str, ExchangePairOpportunityEmbedded] = Field(
        description="Best opportunity for each exchange pair"
    )
    
    # Priority and scheduling
    priority: str = Field(pattern="^(high|medium|low)$")
    scan_frequency: int = Field(gt=0, description="Hours between scans")
    last_opportunity_date: Optional[datetime] = None
    
    # Statistics and analytics
    stats: Dict[str, Any] = Field(default_factory=dict)
    total_opportunities: int = Field(default=0, ge=0)
    best_overall_return: float = Field(default=0.0, ge=0)
    most_profitable_pair: Optional[str] = None
    
    # Analysis metadata
    analysis_timestamp: Indexed(datetime) = Field(default_factory=datetime.now)
    analysis_duration_seconds: Optional[float] = None
    data_sources: List[str] = Field(default_factory=list)
    
    # Tracking
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_scanned_at: Optional[datetime] = None
    next_scan_at: Optional[datetime] = None
    
    # Performance tracking
    historical_performance: Dict[str, Any] = Field(default_factory=dict)
    success_rate: Optional[float] = Field(default=None, ge=0, le=100)
    
    class Settings:
        name = "multi_exchange_opportunities"
        indexes = [
            IndexModel([("symbol", ASCENDING)], unique=True),
            IndexModel([("priority", ASCENDING)]),
            IndexModel([("analysis_timestamp", DESCENDING)]),
            IndexModel([("best_overall_return", DESCENDING)]),
            IndexModel([("total_opportunities", DESCENDING)]),
            IndexModel([("next_scan_at", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            # Compound indexes for analytics
            IndexModel([("symbol", ASCENDING), ("analysis_timestamp", DESCENDING)]),
            IndexModel([("priority", ASCENDING), ("best_overall_return", DESCENDING)]),
            IndexModel([("priority", ASCENDING), ("next_scan_at", ASCENDING)]),
        ]


class AnalysisResultDocument(Document):
    """
    Analysis result document for historical tracking.
    
    NEW for Wiggle - tracks analysis runs and performance metrics.
    """
    
    # Analysis metadata
    analysis_id: Indexed(str) = Field(description="Unique analysis run ID")
    analysis_type: str = Field(description="Type of analysis performed")
    
    # Scope
    tokens_analyzed: List[str] = Field(description="Token symbols analyzed")
    exchanges_used: List[str] = Field(description="Exchanges included in analysis")
    
    # Results summary
    total_opportunities_found: int = Field(default=0, ge=0)
    total_tokens_with_opportunities: int = Field(default=0, ge=0)
    best_opportunity_return: float = Field(default=0.0, ge=0)
    average_opportunity_return: float = Field(default=0.0, ge=0)
    
    # Performance metrics
    analysis_duration_seconds: float = Field(gt=0)
    api_calls_made: int = Field(default=0, ge=0)
    errors_encountered: int = Field(default=0, ge=0)
    
    # Detailed results
    opportunities_by_token: Dict[str, int] = Field(default_factory=dict)
    opportunities_by_exchange_pair: Dict[str, int] = Field(default_factory=dict)
    error_details: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Configuration used
    analysis_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Tracking
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Settings:
        name = "analysis_results"
        indexes = [
            IndexModel([("analysis_id", ASCENDING)]),
            IndexModel([("analysis_type", ASCENDING)]),
            IndexModel([("started_at", DESCENDING)]),
            IndexModel([("completed_at", DESCENDING)]),
            IndexModel([("total_opportunities_found", DESCENDING)]),
            IndexModel([("best_opportunity_return", DESCENDING)]),
        ]