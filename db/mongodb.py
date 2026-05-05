"""
MongoDB Motor client lifecycle and database accessor.

Provides connect_to_mongo(), close_mongo_connection(), and get_database()
for use with FastAPI's lifespan context manager.
"""

import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# Module-level singleton client
_client: Optional[AsyncIOMotorClient] = None


async def connect_to_mongo() -> None:
    """
    Initialise the Motor client from the MONGODB_URI environment variable.

    Raises:
        RuntimeError: If MONGODB_URI is not set or is empty.

    Should be called once during application startup via the lifespan
    context manager.
    """
    global _client

    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        raise RuntimeError(
            "MONGODB_URI environment variable is not set or empty. "
            "Please set MONGODB_URI to a valid MongoDB connection string."
        )

    import certifi
    _client = AsyncIOMotorClient(uri, tlsCAFile=certifi.where())


async def close_mongo_connection() -> None:
    """
    Close the Motor client gracefully.

    Should be called once during application shutdown via the lifespan
    context manager. Safe to call even if connect_to_mongo() was never
    called (no-op in that case).
    """
    global _client

    if _client is not None:
        _client.close()
        _client = None


def get_database() -> AsyncIOMotorDatabase:
    """
    Return the database handle for the configured database.

    The database name is read from the MONGODB_DATABASE environment variable,
    falling back to "skillevate_user" if not set.

    Returns:
        AsyncIOMotorDatabase: The Motor database handle.

    Raises:
        RuntimeError: If called before connect_to_mongo() has been called.
    """
    if _client is None:
        raise RuntimeError(
            "MongoDB client is not initialised. "
            "Ensure connect_to_mongo() is called during application startup."
        )

    db_name = os.getenv("MONGODB_DATABASE", "skillevate_user").strip() or "skillevate_user"
    return _client[db_name]
