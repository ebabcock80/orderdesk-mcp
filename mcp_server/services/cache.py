"""Multi-backend caching system."""

import asyncio
import hashlib
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Any

try:
    import redis.asyncio as redis
except ImportError:
    redis = None
import structlog

from mcp_server.config import settings

logger = structlog.get_logger(__name__)


class CacheBackend(ABC):
    """Abstract cache backend interface."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate keys matching pattern."""
        pass


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend."""

    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """Get value from memory cache."""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry["expires"] > time.time():
                    return entry["value"]
                else:
                    del self._cache[key]
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in memory cache."""
        async with self._lock:
            self._cache[key] = {
                "value": value,
                "expires": time.time() + ttl,
            }

    async def delete(self, key: str) -> None:
        """Delete key from memory cache."""
        async with self._lock:
            self._cache.pop(key, None)

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate keys matching pattern."""
        async with self._lock:
            keys_to_delete = [key for key in self._cache.keys() if pattern in key]
            for key in keys_to_delete:
                del self._cache[key]


class SqliteCacheBackend(CacheBackend):
    """SQLite cache backend."""

    def __init__(self, db_path: str = "/data/cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires INTEGER NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires)")
        conn.commit()
        conn.close()

    async def get(self, key: str) -> Any | None:
        """Get value from SQLite cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT value FROM cache WHERE key = ? AND expires > ?",
            (key, int(time.time())),
        )
        result = cursor.fetchone()
        conn.close()

        if result:
            return json.loads(result[0])
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in SQLite cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires) VALUES (?, ?, ?)",
            (key, json.dumps(value), int(time.time()) + ttl),
        )
        conn.commit()
        conn.close()

    async def delete(self, key: str) -> None:
        """Delete key from SQLite cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
        conn.commit()
        conn.close()

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate keys matching pattern."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM cache WHERE key LIKE ?", (f"%{pattern}%",))
        conn.commit()
        conn.close()


class RedisCacheBackend(CacheBackend):
    """Redis cache backend."""

    def __init__(self, redis_url: str):
        if redis is None:
            raise ImportError("Redis not available. Install with: pip install redis")
        self.redis_url = redis_url
        self._redis: redis.Redis | None = None

    async def _get_redis(self):
        """Get Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def get(self, key: str) -> Any | None:
        """Get value from Redis cache."""
        try:
            redis_client = await self._get_redis()
            value = await redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("redis_get_error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in Redis cache."""
        try:
            redis_client = await self._get_redis()
            await redis_client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error("redis_set_error", key=key, error=str(e))

    async def delete(self, key: str) -> None:
        """Delete key from Redis cache."""
        try:
            redis_client = await self._get_redis()
            await redis_client.delete(key)
        except Exception as e:
            logger.error("redis_delete_error", key=key, error=str(e))

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate keys matching pattern."""
        try:
            redis_client = await self._get_redis()
            keys = await redis_client.keys(f"*{pattern}*")
            if keys:
                await redis_client.delete(*keys)
        except Exception as e:
            logger.error("redis_invalidate_error", pattern=pattern, error=str(e))


class CacheManager:
    """Cache manager with TTL configuration."""

    def __init__(self):
        self.backend = self._create_backend()
        self.ttls = {
            "orders": 15,  # 15 seconds
            "products": 60,  # 1 minute
            "customers": 300,  # 5 minutes
            "store": 3600,  # 1 hour
        }

    def _create_backend(self) -> CacheBackend:
        """Create cache backend based on configuration."""
        backend_type = settings.cache_backend.lower()

        if backend_type == "memory":
            return MemoryCacheBackend()
        elif backend_type == "sqlite":
            return SqliteCacheBackend()
        elif backend_type == "redis":
            if redis is None:
                logger.warning(
                    "redis_not_available",
                    message="Redis not available, falling back to memory cache",
                )
                return MemoryCacheBackend()
            return RedisCacheBackend(settings.redis_url)
        else:
            logger.warning("unknown_cache_backend", backend=backend_type)
            return MemoryCacheBackend()

    def _generate_key(
        self, tenant_id: str, store_id: str, endpoint: str, query_hash: str
    ) -> str:
        """Generate cache key."""
        return f"{tenant_id}:{store_id}:{endpoint}:{query_hash}"

    def _hash_query(self, params: dict | None = None) -> str:
        """Hash query parameters for cache key."""
        if not params:
            return "default"
        return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]

    async def get(
        self,
        tenant_id: str,
        store_id: str,
        endpoint: str,
        params: dict | None = None,
    ) -> Any | None:
        """Get value from cache."""
        query_hash = self._hash_query(params)
        key = self._generate_key(tenant_id, store_id, endpoint, query_hash)
        return await self.backend.get(key)

    async def set(
        self,
        tenant_id: str,
        store_id: str,
        endpoint: str,
        value: Any,
        params: dict | None = None,
    ) -> None:
        """Set value in cache."""
        query_hash = self._hash_query(params)
        key = self._generate_key(tenant_id, store_id, endpoint, query_hash)

        # Determine TTL based on endpoint
        ttl = self.ttls.get(endpoint.split("/")[0], 300)  # Default 5 minutes

        await self.backend.set(key, value, ttl)

    async def invalidate_store(self, tenant_id: str, store_id: str) -> None:
        """Invalidate all cache entries for a store."""
        pattern = f"{tenant_id}:{store_id}:"
        await self.backend.invalidate_pattern(pattern)

    async def invalidate_tenant(self, tenant_id: str) -> None:
        """Invalidate all cache entries for a tenant."""
        pattern = f"{tenant_id}:"
        await self.backend.invalidate_pattern(pattern)


# Global cache manager instance
cache_manager = CacheManager()
