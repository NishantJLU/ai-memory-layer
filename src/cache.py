import json
import redis
import hashlib
from typing import Optional, Any
from src.config import settings

# Initialize Redis client
# Note: In a real enterprise app, we'd use an async redis client like redis-py[hiredis]
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
except Exception as e:
    print(f"Redis connection failed: {e}")
    redis_client = None

def get_cache_key(project_id: str, query: str) -> str:
    """Generate a stable cache key for a query."""
    raw = f"{project_id}:{query}"
    return f"memory_cache:{hashlib.md5(raw.encode('utf-8')).hexdigest()}"

def get_cached_recall(project_id: str, query: str) -> Optional[list]:
    """Retrieve cached recall results."""
    if not redis_client:
        return None
    
    try:
        key = get_cache_key(project_id, query)
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"Cache retrieval failed: {e}")
    return None

def set_cached_recall(project_id: str, query: str, results: list, ttl: int = 300):
    """Cache recall results with a TTL (default 5 minutes)."""
    if not redis_client:
        return
    
    try:
        key = get_cache_key(project_id, query)
        redis_client.setex(key, ttl, json.dumps(results))
    except Exception as e:
        print(f"Cache storage failed: {e}")
