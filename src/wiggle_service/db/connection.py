"""
Database connection management for Wiggle Service.

Provides MongoDB connection using Beanie ODM with async support.
"""

import asyncio
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import structlog

from wiggle_service.core.config import get_settings
# Import models dynamically to avoid circular imports
# from wiggle_service.models.opportunity import (
#     OpportunityDocument,
#     MultiExchangeOpportunityDocument,
#     TokenDocument,
#     ExchangeDocument,
# )

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """
    Database connection manager with connection pooling and health checks.
    
    Enhanced from EventScanner with better error handling and monitoring.
    """
    
    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._database = None
        self._is_connected = False
        self.settings = get_settings()
    
    async def connect(self) -> None:
        """
        Connect to MongoDB and initialize Beanie ODM.
        
        Raises:
            ConnectionError: If connection fails
        """
        if self._is_connected:
            logger.info("Database already connected")
            return
        
        try:
            logger.info("Connecting to MongoDB", url=self.settings.database.mongodb_url)
            
            # Create MongoDB client with connection pooling
            self._client = AsyncIOMotorClient(
                self.settings.database.mongodb_url,
                minPoolSize=self.settings.database.min_pool_size,
                maxPoolSize=self.settings.database.max_pool_size,
                connectTimeoutMS=self.settings.database.connection_timeout_ms,
                serverSelectionTimeoutMS=self.settings.database.server_selection_timeout_ms,
            )
            
            # Get database
            self._database = self._client[self.settings.database.database_name]
            
            # Test connection
            await self._client.admin.command('ping')
            
            # Initialize Beanie with document models (imported dynamically)
            from wiggle_service.models.opportunity import (
                OpportunityDocument,
                MultiExchangeOpportunityDocument,
                TokenDocument,
                ExchangeDocument,
            )
            
            await init_beanie(
                database=self._database,
                document_models=[
                    OpportunityDocument,
                    MultiExchangeOpportunityDocument,
                    TokenDocument,
                    ExchangeDocument,
                ]
            )
            
            self._is_connected = True
            logger.info("MongoDB connection established successfully")
            
        except Exception as e:
            logger.error("Failed to connect to MongoDB", error=str(e))
            await self.disconnect()
            raise ConnectionError(f"Failed to connect to MongoDB: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from MongoDB"""
        if self._client:
            logger.info("Disconnecting from MongoDB")
            self._client.close()
            self._client = None
            self._database = None
            self._is_connected = False
            logger.info("MongoDB connection closed")
    
    async def health_check(self) -> bool:
        """
        Check database connection health.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        if not self._is_connected or not self._client:
            return False
        
        try:
            # Simple ping command
            await self._client.admin.command('ping')
            return True
        except Exception as e:
            logger.warning("Database health check failed", error=str(e))
            return False
    
    async def get_database_stats(self) -> dict:
        """
        Get database statistics for monitoring.
        
        Returns:
            dict: Database statistics
        """
        if not self._is_connected or not self._database:
            return {"status": "disconnected"}
        
        try:
            stats = await self._database.command("dbStats")
            
            # Get collection stats
            collections = {}
            for collection_name in await self._database.list_collection_names():
                collection_stats = await self._database.command(
                    "collStats", collection_name
                )
                collections[collection_name] = {
                    "count": collection_stats.get("count", 0),
                    "size": collection_stats.get("size", 0),
                    "avgObjSize": collection_stats.get("avgObjSize", 0),
                }
            
            return {
                "status": "connected",
                "database": stats.get("db"),
                "collections": len(collections),
                "dataSize": stats.get("dataSize", 0),
                "storageSize": stats.get("storageSize", 0),
                "indexes": stats.get("indexes", 0),
                "collectionsDetail": collections,
            }
            
        except Exception as e:
            logger.error("Failed to get database stats", error=str(e))
            return {"status": "error", "error": str(e)}
    
    @property
    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self._is_connected
    
    @property
    def client(self) -> Optional[AsyncIOMotorClient]:
        """Get the MongoDB client"""
        return self._client
    
    @property
    def database(self):
        """Get the database instance"""
        return self._database


# Global database manager instance
db_manager = DatabaseManager()


async def get_database():
    """
    Get the database instance (for dependency injection).
    
    Returns:
        Database instance
    """
    if not db_manager.is_connected:
        await db_manager.connect()
    return db_manager.database


async def init_database():
    """Initialize database connection"""
    await db_manager.connect()


async def close_database():
    """Close database connection"""
    await db_manager.disconnect()


# Context manager for database transactions (if needed)
class DatabaseTransaction:
    """
    Context manager for database transactions.
    
    Note: MongoDB transactions require replica set or sharded cluster.
    """
    
    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
        self.session = None
    
    async def __aenter__(self):
        self.session = await self.client.start_session()
        await self.session.start_transaction()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.session.abort_transaction()
        else:
            await self.session.commit_transaction()
        await self.session.end_session()