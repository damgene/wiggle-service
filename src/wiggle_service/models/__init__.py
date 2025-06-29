"""
MongoDB document models for Wiggle Service.
"""

from .opportunity import (
    TokenDocument,
    ExchangeDocument,
    OpportunityDocument,
    ExchangePairOpportunityEmbedded,
    MultiExchangeOpportunityDocument,
    AnalysisResultDocument,
)

__all__ = [
    "TokenDocument",
    "ExchangeDocument", 
    "OpportunityDocument",
    "ExchangePairOpportunityEmbedded",
    "MultiExchangeOpportunityDocument",
    "AnalysisResultDocument",
]