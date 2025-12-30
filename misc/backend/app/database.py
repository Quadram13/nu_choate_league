"""
MongoDB database connection and utilities
"""
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from app.config import settings


class Database:
    """MongoDB database connection manager"""
    client: Optional[AsyncIOMotorClient] = None
    

# Global database instance
db = Database()


async def connect_to_mongo():
    """Connect to MongoDB"""
    print(f"Connecting to MongoDB...")
    db.client = AsyncIOMotorClient(settings.MONGODB_URI)
    
    # Test connection
    try:
        await db.client.admin.command('ping')
        print("✓ Successfully connected to MongoDB")
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close MongoDB connection"""
    if db.client:
        db.client.close()
        print("✓ MongoDB connection closed")


def get_database():
    """Get database instance"""
    return db.client[settings.DATABASE_NAME]
