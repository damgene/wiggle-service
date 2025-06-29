"""
Exchange endpoints for Wiggle Service.

Exchange management and monitoring.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
import structlog

from wiggle_common.models import ExchangeType, ChainType
from wiggle_service.models import ExchangeDocument
from wiggle_service.db import get_database

logger = structlog.get_logger(__name__)

router = APIRouter()


class ExchangeResponse(BaseModel):
    """Response model for exchanges"""
    id: str
    name: str
    exchange_type: ExchangeType
    is_active: bool
    rate_limit_per_minute: int
    supports_historical_data: bool
    supports_websocket: bool
    supported_chains: List[ChainType]
    total_requests: int
    total_errors: int
    consecutive_errors: int
    last_successful_request: Optional[str]
    average_response_time_ms: Optional[float]


@router.get("/", summary="List exchanges")
async def list_exchanges(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    exchange_type: Optional[ExchangeType] = Query(None, description="Filter by exchange type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db=Depends(get_database)
):
    """List exchanges with filtering and pagination"""
    try:
        # Build filters
        filters = {}
        if exchange_type:
            filters["exchange_type"] = exchange_type
        if is_active is not None:
            filters["is_active"] = is_active
        
        # Execute query
        skip = (page - 1) * page_size
        
        query = ExchangeDocument.find(filters)
        total = await ExchangeDocument.count_documents(filters)
        
        exchanges = await query.sort([("name", 1)]).skip(skip).limit(page_size).to_list()
        
        # Convert to response format
        exchange_responses = [
            ExchangeResponse(
                id=str(exchange.id),
                name=exchange.name,
                exchange_type=exchange.exchange_type,
                is_active=exchange.is_active,
                rate_limit_per_minute=exchange.rate_limit_per_minute,
                supports_historical_data=exchange.supports_historical_data,
                supports_websocket=exchange.supports_websocket,
                supported_chains=exchange.supported_chains,
                total_requests=exchange.total_requests,
                total_errors=exchange.total_errors,
                consecutive_errors=exchange.consecutive_errors,
                last_successful_request=exchange.last_successful_request.isoformat() if exchange.last_successful_request else None,
                average_response_time_ms=exchange.average_response_time_ms,
            )
            for exchange in exchanges
        ]
        
        return {
            "exchanges": exchange_responses,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": skip + page_size < total,
        }
        
    except Exception as e:
        logger.error("Failed to list exchanges", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve exchanges")


@router.get("/{exchange_id}", response_model=ExchangeResponse, summary="Get exchange")
async def get_exchange(exchange_id: str, db=Depends(get_database)):
    """Get a specific exchange by ID"""
    try:
        exchange = await ExchangeDocument.get(exchange_id)
        if not exchange:
            raise HTTPException(status_code=404, detail="Exchange not found")
        
        return ExchangeResponse(
            id=str(exchange.id),
            name=exchange.name,
            exchange_type=exchange.exchange_type,
            is_active=exchange.is_active,
            rate_limit_per_minute=exchange.rate_limit_per_minute,
            supports_historical_data=exchange.supports_historical_data,
            supports_websocket=exchange.supports_websocket,
            supported_chains=exchange.supported_chains,
            total_requests=exchange.total_requests,
            total_errors=exchange.total_errors,
            consecutive_errors=exchange.consecutive_errors,
            last_successful_request=exchange.last_successful_request.isoformat() if exchange.last_successful_request else None,
            average_response_time_ms=exchange.average_response_time_ms,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get exchange", exchange_id=exchange_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve exchange")


@router.get("/health/summary", summary="Exchange health summary")
async def get_exchange_health_summary(db=Depends(get_database)):
    """Get summary of exchange health status"""
    try:
        # Get all exchanges
        exchanges = await ExchangeDocument.find_all().to_list()
        
        # Calculate health metrics
        total_exchanges = len(exchanges)
        active_exchanges = sum(1 for ex in exchanges if ex.is_active)
        healthy_exchanges = sum(1 for ex in exchanges if ex.is_active and ex.consecutive_errors < 3)
        
        # Calculate error rates
        total_requests = sum(ex.total_requests for ex in exchanges)
        total_errors = sum(ex.total_errors for ex in exchanges)
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
        
        # Get exchanges with issues
        unhealthy_exchanges = [
            {
                "name": ex.name,
                "consecutive_errors": ex.consecutive_errors,
                "last_error": ex.last_error,
                "is_active": ex.is_active,
            }
            for ex in exchanges
            if ex.consecutive_errors >= 3 or not ex.is_active
        ]
        
        return {
            "total_exchanges": total_exchanges,
            "active_exchanges": active_exchanges,
            "healthy_exchanges": healthy_exchanges,
            "error_rate_percent": round(error_rate, 2),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "unhealthy_exchanges": unhealthy_exchanges,
        }
        
    except Exception as e:
        logger.error("Failed to get exchange health summary", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve health summary")