"""
Opportunity endpoints for Wiggle Service.

CRUD operations and queries for arbitrage opportunities.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
import structlog

from wiggle_common.models import OpportunityClass, RiskLevel
from wiggle_service.models import (
    OpportunityDocument,
    MultiExchangeOpportunityDocument,
)
from wiggle_service.db import get_database

logger = structlog.get_logger(__name__)

router = APIRouter()


class OpportunityCreateRequest(BaseModel):
    """Request model for creating opportunities"""
    opportunity_class: OpportunityClass
    estimated_return_percent: float = Field(ge=0)
    capital_required_usd: float = Field(gt=0)
    duration_hours: float = Field(gt=0)
    risk_level: RiskLevel
    source_exchanges: List[str] = Field(min_items=1)
    token_symbol: Optional[str] = None
    token_name: Optional[str] = None
    gas_cost_usd: float = Field(default=35.0, ge=0)
    trading_fees_percent: float = Field(default=0.6, ge=0)
    notes: str = Field(default="")


class OpportunityResponse(BaseModel):
    """Response model for opportunities"""
    id: str
    opportunity_class: OpportunityClass
    estimated_return_percent: float
    capital_required_usd: float
    net_return_percent: Optional[float]
    duration_hours: float
    risk_level: RiskLevel
    source_exchanges: List[str]
    token_symbol: Optional[str]
    confidence_score: float
    is_executed: bool
    created_at: datetime
    updated_at: datetime


class OpportunityListResponse(BaseModel):
    """Response model for opportunity lists"""
    opportunities: List[OpportunityResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class MultiExchangeOpportunityResponse(BaseModel):
    """Response model for multi-exchange opportunities"""
    id: str
    symbol: str
    name: str
    total_opportunities: int
    best_overall_return: float
    priority: str
    supported_exchanges: List[str]
    analysis_timestamp: datetime
    next_scan_at: Optional[datetime]


@router.get("/", response_model=OpportunityListResponse, summary="List opportunities")
async def list_opportunities(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    token_symbol: Optional[str] = Query(None, description="Filter by token symbol"),
    opportunity_class: Optional[OpportunityClass] = Query(None, description="Filter by class"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    min_return: Optional[float] = Query(None, ge=0, description="Minimum return percentage"),
    is_executed: Optional[bool] = Query(None, description="Filter by execution status"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_desc: bool = Query(True, description="Sort descending"),
    db=Depends(get_database)
):
    """
    List opportunities with filtering and pagination.
    
    Supports filtering by multiple criteria and sorting options.
    """
    try:
        # Build query filters
        filters = {}
        if token_symbol:
            filters["token_symbol"] = token_symbol
        if opportunity_class:
            filters["opportunity_class"] = opportunity_class
        if risk_level:
            filters["risk_level"] = risk_level
        if min_return is not None:
            filters["estimated_return_percent"] = {"$gte": min_return}
        if is_executed is not None:
            filters["is_executed"] = is_executed
        
        # Build sort criteria
        sort_direction = -1 if sort_desc else 1
        sort_criteria = [(sort_by, sort_direction)]
        
        # Execute query with pagination
        skip = (page - 1) * page_size
        
        query = OpportunityDocument.find(filters)
        total = await OpportunityDocument.count_documents(filters)
        
        opportunities = await query.sort(sort_criteria).skip(skip).limit(page_size).to_list()
        
        # Convert to response format
        opportunity_responses = [
            OpportunityResponse(
                id=str(opp.id),
                opportunity_class=opp.opportunity_class,
                estimated_return_percent=opp.estimated_return_percent,
                capital_required_usd=opp.capital_required_usd,
                net_return_percent=opp.net_return_percent,
                duration_hours=opp.duration_hours,
                risk_level=opp.risk_level,
                source_exchanges=opp.source_exchanges,
                token_symbol=opp.token_symbol,
                confidence_score=opp.confidence_score,
                is_executed=opp.is_executed,
                created_at=opp.created_at,
                updated_at=opp.updated_at,
            )
            for opp in opportunities
        ]
        
        has_next = skip + page_size < total
        
        return OpportunityListResponse(
            opportunities=opportunity_responses,
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next,
        )
        
    except Exception as e:
        logger.error("Failed to list opportunities", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve opportunities")


@router.get("/multi-exchange", summary="List multi-exchange opportunities")
async def list_multi_exchange_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    symbol: Optional[str] = Query(None, description="Filter by token symbol"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    min_return: Optional[float] = Query(None, ge=0),
    db=Depends(get_database)
):
    """List multi-exchange opportunities with filtering"""
    try:
        # Build filters
        filters = {}
        if symbol:
            filters["symbol"] = symbol
        if priority:
            filters["priority"] = priority
        if min_return is not None:
            filters["best_overall_return"] = {"$gte": min_return}
        
        # Execute query
        skip = (page - 1) * page_size
        
        query = MultiExchangeOpportunityDocument.find(filters)
        total = await MultiExchangeOpportunityDocument.count_documents(filters)
        
        opportunities = await query.sort([("best_overall_return", -1)]).skip(skip).limit(page_size).to_list()
        
        # Convert to response format
        responses = [
            MultiExchangeOpportunityResponse(
                id=str(opp.id),
                symbol=opp.symbol,
                name=opp.name,
                total_opportunities=opp.total_opportunities,
                best_overall_return=opp.best_overall_return,
                priority=opp.priority,
                supported_exchanges=opp.supported_exchanges,
                analysis_timestamp=opp.analysis_timestamp,
                next_scan_at=opp.next_scan_at,
            )
            for opp in opportunities
        ]
        
        return {
            "opportunities": responses,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": skip + page_size < total,
        }
        
    except Exception as e:
        logger.error("Failed to list multi-exchange opportunities", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve opportunities")


@router.get("/{opportunity_id}", response_model=OpportunityResponse, summary="Get opportunity")
async def get_opportunity(opportunity_id: str, db=Depends(get_database)):
    """Get a specific opportunity by ID"""
    try:
        opportunity = await OpportunityDocument.get(opportunity_id)
        if not opportunity:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        return OpportunityResponse(
            id=str(opportunity.id),
            opportunity_class=opportunity.opportunity_class,
            estimated_return_percent=opportunity.estimated_return_percent,
            capital_required_usd=opportunity.capital_required_usd,
            net_return_percent=opportunity.net_return_percent,
            duration_hours=opportunity.duration_hours,
            risk_level=opportunity.risk_level,
            source_exchanges=opportunity.source_exchanges,
            token_symbol=opportunity.token_symbol,
            confidence_score=opportunity.confidence_score,
            is_executed=opportunity.is_executed,
            created_at=opportunity.created_at,
            updated_at=opportunity.updated_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get opportunity", opportunity_id=opportunity_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve opportunity")


@router.post("/", response_model=OpportunityResponse, summary="Create opportunity")
async def create_opportunity(request: OpportunityCreateRequest, db=Depends(get_database)):
    """Create a new opportunity"""
    try:
        # Calculate net return
        gas_impact = (request.gas_cost_usd / request.capital_required_usd) * 100
        net_return = request.estimated_return_percent - gas_impact - request.trading_fees_percent
        
        # Create opportunity document
        opportunity = OpportunityDocument(
            opportunity_class=request.opportunity_class,
            estimated_return_percent=request.estimated_return_percent,
            capital_required_usd=request.capital_required_usd,
            net_return_percent=net_return,
            duration_hours=request.duration_hours,
            risk_level=request.risk_level,
            source_exchanges=request.source_exchanges,
            token_symbol=request.token_symbol,
            token_name=request.token_name,
            gas_cost_usd=request.gas_cost_usd,
            trading_fees_percent=request.trading_fees_percent,
            notes=request.notes,
        )
        
        # Save to database
        await opportunity.save()
        
        logger.info("Created new opportunity", opportunity_id=str(opportunity.id))
        
        return OpportunityResponse(
            id=str(opportunity.id),
            opportunity_class=opportunity.opportunity_class,
            estimated_return_percent=opportunity.estimated_return_percent,
            capital_required_usd=opportunity.capital_required_usd,
            net_return_percent=opportunity.net_return_percent,
            duration_hours=opportunity.duration_hours,
            risk_level=opportunity.risk_level,
            source_exchanges=opportunity.source_exchanges,
            token_symbol=opportunity.token_symbol,
            confidence_score=opportunity.confidence_score,
            is_executed=opportunity.is_executed,
            created_at=opportunity.created_at,
            updated_at=opportunity.updated_at,
        )
        
    except Exception as e:
        logger.error("Failed to create opportunity", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create opportunity")


@router.get("/stats/summary", summary="Get opportunity statistics")
async def get_opportunity_stats(db=Depends(get_database)):
    """Get summary statistics for opportunities"""
    try:
        # Basic counts
        total_opportunities = await OpportunityDocument.count_documents({})
        executed_opportunities = await OpportunityDocument.count_documents({"is_executed": True})
        pending_opportunities = total_opportunities - executed_opportunities
        
        # Recent opportunities (last 24 hours)
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_opportunities = await OpportunityDocument.count_documents({
            "created_at": {"$gte": recent_cutoff}
        })
        
        # Aggregation for return statistics
        pipeline = [
            {"$group": {
                "_id": None,
                "avg_return": {"$avg": "$estimated_return_percent"},
                "max_return": {"$max": "$estimated_return_percent"},
                "min_return": {"$min": "$estimated_return_percent"},
            }}
        ]
        
        return_stats = await OpportunityDocument.aggregate(pipeline).to_list(1)
        return_data = return_stats[0] if return_stats else {}
        
        return {
            "total_opportunities": total_opportunities,
            "executed_opportunities": executed_opportunities,
            "pending_opportunities": pending_opportunities,
            "recent_opportunities_24h": recent_opportunities,
            "return_statistics": {
                "average_return_percent": return_data.get("avg_return", 0.0),
                "max_return_percent": return_data.get("max_return", 0.0),
                "min_return_percent": return_data.get("min_return", 0.0),
            }
        }
        
    except Exception as e:
        logger.error("Failed to get opportunity stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")