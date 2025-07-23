"""
Cache Manager with LRU eviction and size limits
"""
import asyncio
from collections import OrderedDict
from typing import Any, Dict, Optional, TypeVar, Generic
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LRUCache(Generic[T]):
    """Thread-safe LRU cache with size limit"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: Optional[int] = None):
        """
        Initialize LRU cache
        
        Args:
            max_size: Maximum number of items in cache
            ttl_seconds: Time to live for cache items (optional)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[T, datetime]] = OrderedDict()
        self._lock = asyncio.Lock()
        
    async def get(self, key: str) -> Optional[T]:
        """Get item from cache"""
        async with self._lock:
            if key not in self._cache:
                return None
                
            value, timestamp = self._cache[key]
            
            # Check TTL if configured
            if self.ttl_seconds:
                if datetime.now() - timestamp > timedelta(seconds=self.ttl_seconds):
                    del self._cache[key]
                    return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return value
    
    async def set(self, key: str, value: T) -> None:
        """Set item in cache"""
        async with self._lock:
            # Remove oldest item if at capacity
            if key not in self._cache and len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Evicted oldest cache item: {oldest_key}")
            
            # Add or update item
            self._cache[key] = (value, datetime.now())
            
            # Move to end if updating
            if key in self._cache:
                self._cache.move_to_end(key)
    
    async def delete(self, key: str) -> bool:
        """Delete item from cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all items from cache"""
        async with self._lock:
            self._cache.clear()
    
    async def size(self) -> int:
        """Get current cache size"""
        async with self._lock:
            return len(self._cache)
    
    async def cleanup_expired(self) -> int:
        """Remove expired items from cache"""
        if not self.ttl_seconds:
            return 0
            
        async with self._lock:
            current_time = datetime.now()
            expired_keys = []
            
            for key, (value, timestamp) in self._cache.items():
                if current_time - timestamp > timedelta(seconds=self.ttl_seconds):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache items")
            
            return len(expired_keys)


class CacheManager:
    """Manages multiple caches for different purposes"""
    
    def __init__(self):
        """Initialize cache manager with different cache types"""
        # Different caches for different purposes with appropriate limits
        self.adapter_cache = LRUCache[Dict[str, Any]](max_size=8)  # Limited by vLLM
        self.task_cache = LRUCache[Dict[str, Any]](max_size=1000, ttl_seconds=3600)  # 1 hour TTL
        self.response_cache = LRUCache[str](max_size=500, ttl_seconds=600)  # 10 min TTL
        self.tts_task_cache = LRUCache[Dict[str, Any]](max_size=100, ttl_seconds=3600)  # 1 hour TTL
        
    async def periodic_cleanup(self):
        """Periodically clean up expired items from all caches"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Cleanup expired items
                adapter_expired = await self.adapter_cache.cleanup_expired()
                task_expired = await self.task_cache.cleanup_expired()
                response_expired = await self.response_cache.cleanup_expired()
                tts_expired = await self.tts_task_cache.cleanup_expired()
                
                total_expired = adapter_expired + task_expired + response_expired + tts_expired
                
                if total_expired > 0:
                    logger.info(f"Periodic cleanup removed {total_expired} expired items")
                    
                # Log cache sizes
                logger.debug(f"Cache sizes - Adapters: {await self.adapter_cache.size()}, "
                           f"Tasks: {await self.task_cache.size()}, "
                           f"Responses: {await self.response_cache.size()}, "
                           f"TTS: {await self.tts_task_cache.size()}")
                           
            except Exception as e:
                logger.error(f"Error during periodic cleanup: {e}")


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None
_cache_manager_lock = asyncio.Lock()


async def get_cache_manager() -> CacheManager:
    """Get or create cache manager instance (thread-safe)"""
    global _cache_manager
    async with _cache_manager_lock:
        if _cache_manager is None:
            _cache_manager = CacheManager()
            # Start periodic cleanup task
            asyncio.create_task(_cache_manager.periodic_cleanup())
    return _cache_manager