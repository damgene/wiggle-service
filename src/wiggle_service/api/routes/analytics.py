"""
Analytics endpoints for Wiggle Service.

Analytics and reporting for opportunities and performance.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends, status
from pydantic import BaseModel, Field
import structlog
from uuid import uuid4

from wiggle_service.models import (
    OpportunityDocument,
    MultiExchangeOpportunityDocument,
    AnalysisResultDocument,
)
from wiggle_service.db import get_database

logger = structlog.get_logger(__name__)

router = APIRouter()


class AnalyticsTimeRange(BaseModel):
    """Analytics time range response"""
    start_date: datetime
    end_date: datetime
    total_opportunities: int
    total_return_percent: float
    average_return_percent: float
    max_return_percent: float
    unique_tokens: int


class TokenPerformance(BaseModel):
    """Token performance metrics"""
    symbol: str
    total_opportunities: int
    average_return: float
    max_return: float
    total_volume_usd: float


class ExchangePairAnalytics(BaseModel):
    """Exchange pair analytics"""
    pair_name: str
    total_opportunities: int
    average_return: float
    max_return: float
    success_rate: float


class AnalysisResultSubmission(BaseModel):
    """Analysis result submission from wiggle-finder"""
    analysis_id: str
    analysis_type: str
    tokens_analyzed: List[str]
    exchanges_used: List[str]
    total_opportunities_found: int = Field(default=0, ge=0)
    total_tokens_with_opportunities: int = Field(default=0, ge=0)
    best_opportunity_return: float = Field(default=0.0, ge=0)
    average_opportunity_return: float = Field(default=0.0, ge=0)
    analysis_duration_seconds: float = Field(gt=0)
    api_calls_made: int = Field(default=0, ge=0)
    errors_encountered: int = Field(default=0, ge=0)
    opportunities_by_token: Dict[str, int] = Field(default_factory=dict)
    opportunities_by_exchange_pair: Dict[str, int] = Field(default_factory=dict)
    analysis_config: Dict[str, Any] = Field(default_factory=dict)
    started_at: str = Field(description="ISO datetime string")
    completed_at: str = Field(description="ISO datetime string")


@router.post("/analysis-results", 
             summary="Submit analysis results",
             status_code=status.HTTP_201_CREATED)
async def submit_analysis_result(
    analysis_result: AnalysisResultSubmission,
    db=Depends(get_database)
):
    """Submit analysis results from wiggle-finder for tracking and historical analysis"""
    try:
        # Parse datetime strings
        started_at = datetime.fromisoformat(analysis_result.started_at.replace('Z', '+00:00'))
        completed_at = datetime.fromisoformat(analysis_result.completed_at.replace('Z', '+00:00'))
        
        # Create database document
        result_doc = AnalysisResultDocument(
            analysis_id=analysis_result.analysis_id,
            analysis_type=analysis_result.analysis_type,
            tokens_analyzed=analysis_result.tokens_analyzed,
            exchanges_used=analysis_result.exchanges_used,
            total_opportunities_found=analysis_result.total_opportunities_found,
            total_tokens_with_opportunities=analysis_result.total_tokens_with_opportunities,
            best_opportunity_return=analysis_result.best_opportunity_return,
            average_opportunity_return=analysis_result.average_opportunity_return,
            analysis_duration_seconds=analysis_result.analysis_duration_seconds,
            api_calls_made=analysis_result.api_calls_made,
            errors_encountered=analysis_result.errors_encountered,
            opportunities_by_token=analysis_result.opportunities_by_token,
            opportunities_by_exchange_pair=analysis_result.opportunities_by_exchange_pair,
            analysis_config=analysis_result.analysis_config,
            started_at=started_at,
            completed_at=completed_at,
            created_at=datetime.now()
        )
        
        # Save to database
        await result_doc.save()
        
        logger.info("Analysis result submitted successfully", 
                   analysis_id=analysis_result.analysis_id,
                   analysis_type=analysis_result.analysis_type,
                   tokens_count=len(analysis_result.tokens_analyzed),
                   opportunities_found=analysis_result.total_opportunities_found)
        
        return {
            "status": "success",
            "message": "Analysis result submitted successfully",
            "analysis_id": analysis_result.analysis_id,
            "document_id": str(result_doc.id)
        }
        
    except ValueError as e:
        logger.error("Invalid datetime format in analysis result", 
                    analysis_id=analysis_result.analysis_id, 
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid datetime format: {str(e)}"
        )
    except Exception as e:
        logger.error("Failed to submit analysis result", 
                    analysis_id=analysis_result.analysis_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit analysis result"
        )


@router.get("/overview", summary="Analytics overview")
async def get_analytics_overview(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db=Depends(get_database)
):
    """Get analytics overview for the specified time period"""
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Basic opportunity metrics
        filters = {"created_at": {"$gte": start_date, "$lte": end_date}}
        opportunities = await OpportunityDocument.find(filters).to_list()
        
        if not opportunities:
            return {
                "time_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days,
                },
                "opportunities": {
                    "total": 0,
                    "executed": 0,
                    "pending": 0,
                    "average_return": 0.0,
                    "max_return": 0.0,
                },
                "tokens": {"unique_count": 0},
                "exchanges": {"unique_count": 0},
            }
        
        # Calculate metrics
        total_opportunities = len(opportunities)
        executed_opportunities = sum(1 for opp in opportunities if opp.is_executed)
        pending_opportunities = total_opportunities - executed_opportunities
        
        returns = [opp.estimated_return_percent for opp in opportunities]
        average_return = sum(returns) / len(returns)
        max_return = max(returns)
        
        # Unique counts
        unique_tokens = len(set(opp.token_symbol for opp in opportunities if opp.token_symbol))
        unique_exchanges = len(set(
            exchange 
            for opp in opportunities 
            for exchange in opp.source_exchanges
        ))
        
        return {
            "time_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            "opportunities": {
                "total": total_opportunities,
                "executed": executed_opportunities,
                "pending": pending_opportunities,
                "average_return": round(average_return, 2),
                "max_return": round(max_return, 2),
            },
            "tokens": {"unique_count": unique_tokens},
            "exchanges": {"unique_count": unique_exchanges},
        }
        
    except Exception as e:
        logger.error("Failed to get analytics overview", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics overview")


@router.get("/tokens/performance", summary="Token performance analytics")
async def get_token_performance(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_database)
):
    """Get token performance analytics"""
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Aggregation pipeline for token performance
        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": start_date, "$lte": end_date},
                    "token_symbol": {"$ne": None}
                }
            },
            {
                "$group": {
                    "_id": "$token_symbol",
                    "total_opportunities": {"$sum": 1},
                    "average_return": {"$avg": "$estimated_return_percent"},
                    "max_return": {"$max": "$estimated_return_percent"},
                    "total_capital": {"$sum": "$capital_required_usd"},
                }
            },
            {
                "$sort": {"average_return": -1}
            },
            {
                "$limit": limit
            }
        ]
        
        results = await OpportunityDocument.aggregate(pipeline).to_list(limit)
        
        performance_data = [
            TokenPerformance(
                symbol=result["_id"],
                total_opportunities=result["total_opportunities"],
                average_return=round(result["average_return"], 2),
                max_return=round(result["max_return"], 2),
                total_volume_usd=round(result["total_capital"], 2),
            )
            for result in results
        ]
        
        return {
            "time_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            "tokens": performance_data,
            "total_tokens": len(performance_data),
        }
        
    except Exception as e:
        logger.error("Failed to get token performance", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve token performance")


@router.get("/exchange-pairs", summary="Exchange pair analytics")
async def get_exchange_pair_analytics(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_database)
):
    """Get exchange pair analytics from multi-exchange opportunities"""
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get multi-exchange opportunities in date range
        multi_opps = await MultiExchangeOpportunityDocument.find({
            "analysis_timestamp": {"$gte": start_date, "$lte": end_date}
        }).to_list()
        
        # Aggregate exchange pair data
        pair_analytics = {}
        
        for opp in multi_opps:
            for pair_name, pair_opportunities in opp.exchange_pair_opportunities.items():
                if pair_name not in pair_analytics:
                    pair_analytics[pair_name] = {
                        "total_opportunities": 0,
                        "returns": [],
                        "success_count": 0,
                        "total_count": 0,
                    }
                
                pair_data = pair_analytics[pair_name]
                pair_data["total_opportunities"] += len(pair_opportunities)
                
                for pair_opp in pair_opportunities:
                    pair_data["returns"].append(pair_opp.return_percent)
                    pair_data["total_count"] += 1
                    if pair_opp.return_percent > 6.0:  # EventScanner profitability threshold
                        pair_data["success_count"] += 1
        
        # Convert to response format
        analytics_results = []
        for pair_name, data in pair_analytics.items():
            if data["returns"]:
                average_return = sum(data["returns"]) / len(data["returns"])
                max_return = max(data["returns"])
                success_rate = (data["success_count"] / data["total_count"]) * 100
                
                analytics_results.append(ExchangePairAnalytics(
                    pair_name=pair_name,
                    total_opportunities=data["total_opportunities"],
                    average_return=round(average_return, 2),
                    max_return=round(max_return, 2),
                    success_rate=round(success_rate, 2),
                ))
        
        # Sort by average return
        analytics_results.sort(key=lambda x: x.average_return, reverse=True)
        
        return {
            "time_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            "exchange_pairs": analytics_results[:limit],
            "total_pairs": len(analytics_results),
        }
        
    except Exception as e:
        logger.error("Failed to get exchange pair analytics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve exchange pair analytics")


@router.get("/analysis-history", summary="Analysis run history")
async def get_analysis_history(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db=Depends(get_database)
):
    """Get history of analysis runs"""
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get analysis results
        analyses = await AnalysisResultDocument.find({
            "started_at": {"$gte": start_date, "$lte": end_date}
        }).sort([("started_at", -1)]).limit(limit).to_list()
        
        return {
            "time_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            "analyses": [
                {
                    "id": str(analysis.id),
                    "analysis_id": analysis.analysis_id,
                    "analysis_type": analysis.analysis_type,
                    "tokens_analyzed": len(analysis.tokens_analyzed),
                    "exchanges_used": len(analysis.exchanges_used),
                    "total_opportunities_found": analysis.total_opportunities_found,
                    "best_opportunity_return": analysis.best_opportunity_return,
                    "average_opportunity_return": analysis.average_opportunity_return,
                    "duration_seconds": analysis.analysis_duration_seconds,
                    "api_calls_made": analysis.api_calls_made,
                    "errors_encountered": analysis.errors_encountered,
                    "started_at": analysis.started_at.isoformat(),
                    "completed_at": analysis.completed_at.isoformat(),
                }
                for analysis in analyses
            ],
            "total_analyses": len(analyses),
        }
        
    except Exception as e:
        logger.error("Failed to get analysis history", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve analysis history")