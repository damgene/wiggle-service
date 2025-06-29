"""
Token endpoints for Wiggle Service.

CRUD operations for token management.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
import structlog

from wiggle_common.models import ChainType
from wiggle_service.models import TokenDocument
from wiggle_service.db import get_database

logger = structlog.get_logger(__name__)

router = APIRouter()


class TokenCreateRequest(BaseModel):
    """Request model for creating tokens"""
    symbol: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    address: Optional[str] = None
    chain: ChainType
    decimals: Optional[int] = Field(default=18, ge=0, le=18)
    coingecko_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    notes: str = Field(default="")


class TokenResponse(BaseModel):
    """Response model for tokens"""
    id: str
    symbol: str
    name: str
    address: Optional[str]
    chain: ChainType
    decimals: Optional[int]
    coingecko_id: Optional[str]
    is_active: bool
    tags: List[str]
    notes: str


@router.get("/", summary="List tokens")
async def list_tokens(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    chain: Optional[ChainType] = Query(None, description="Filter by chain"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db=Depends(get_database)
):
    """List tokens with filtering and pagination"""
    try:
        # Build filters
        filters = {}
        if symbol:
            filters["symbol"] = {"$regex": symbol, "$options": "i"}  # Case-insensitive search
        if chain:
            filters["chain"] = chain
        if is_active is not None:
            filters["is_active"] = is_active
        
        # Execute query
        skip = (page - 1) * page_size
        
        query = TokenDocument.find(filters)
        total = await TokenDocument.count_documents(filters)
        
        tokens = await query.sort([("symbol", 1)]).skip(skip).limit(page_size).to_list()
        
        # Convert to response format
        token_responses = [
            TokenResponse(
                id=str(token.id),
                symbol=token.symbol,
                name=token.name,
                address=token.address,
                chain=token.chain,
                decimals=token.decimals,
                coingecko_id=token.coingecko_id,
                is_active=token.is_active,
                tags=token.tags,
                notes=token.notes,
            )
            for token in tokens
        ]
        
        return {
            "tokens": token_responses,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": skip + page_size < total,
        }
        
    except Exception as e:
        logger.error("Failed to list tokens", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve tokens")


@router.get("/{token_id}", response_model=TokenResponse, summary="Get token")
async def get_token(token_id: str, db=Depends(get_database)):
    """Get a specific token by ID"""
    try:
        token = await TokenDocument.get(token_id)
        if not token:
            raise HTTPException(status_code=404, detail="Token not found")
        
        return TokenResponse(
            id=str(token.id),
            symbol=token.symbol,
            name=token.name,
            address=token.address,
            chain=token.chain,
            decimals=token.decimals,
            coingecko_id=token.coingecko_id,
            is_active=token.is_active,
            tags=token.tags,
            notes=token.notes,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get token", token_id=token_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve token")


@router.post("/", response_model=TokenResponse, summary="Create token")
async def create_token(request: TokenCreateRequest, db=Depends(get_database)):
    """Create a new token"""
    try:
        # Check for existing token with same symbol and chain
        existing = await TokenDocument.find_one({
            "symbol": request.symbol,
            "chain": request.chain
        })
        
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Token {request.symbol} already exists on {request.chain}"
            )
        
        # Create token document
        token = TokenDocument(
            symbol=request.symbol,
            name=request.name,
            address=request.address,
            chain=request.chain,
            decimals=request.decimals,
            coingecko_id=request.coingecko_id,
            tags=request.tags,
            notes=request.notes,
        )
        
        # Save to database
        await token.save()
        
        logger.info("Created new token", token_id=str(token.id), symbol=request.symbol)
        
        return TokenResponse(
            id=str(token.id),
            symbol=token.symbol,
            name=token.name,
            address=token.address,
            chain=token.chain,
            decimals=token.decimals,
            coingecko_id=token.coingecko_id,
            is_active=token.is_active,
            tags=token.tags,
            notes=token.notes,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create token", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create token")


@router.get("/search/{symbol}", summary="Search tokens by symbol")
async def search_tokens_by_symbol(
    symbol: str,
    limit: int = Query(10, ge=1, le=50),
    db=Depends(get_database)
):
    """Search tokens by symbol (case-insensitive)"""
    try:
        # Case-insensitive regex search
        tokens = await TokenDocument.find({
            "symbol": {"$regex": symbol, "$options": "i"},
            "is_active": True
        }).limit(limit).to_list()
        
        return [
            {
                "id": str(token.id),
                "symbol": token.symbol,
                "name": token.name,
                "chain": token.chain,
                "address": token.address,
            }
            for token in tokens
        ]
        
    except Exception as e:
        logger.error("Failed to search tokens", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to search tokens")