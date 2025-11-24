import redis.asyncio as aioredis
from typing import Optional, Dict, Any
import orjson


class IdempotencyManager:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.ttl_seconds = 86400

    def _get_key(self, idempotency_key: str) -> str:
        return f"idempotency:{idempotency_key}"

    async def get_response(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        key = self._get_key(idempotency_key)
        
        data = await self.redis.get(key)
        
        if data:
            return orjson.loads(data)
        
        return None

    async def store_response(
        self,
        idempotency_key: str,
        response_data: Dict[str, Any]
    ) -> None:
        key = self._get_key(idempotency_key)
        
        serialized = orjson.dumps(
            response_data,
            option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_PASSTHROUGH_DATETIME
        )
        
        await self.redis.setex(key, self.ttl_seconds, serialized)

    async def exists(self, idempotency_key: str) -> bool:
        key = self._get_key(idempotency_key)
        return await self.redis.exists(key) > 0

    async def delete(self, idempotency_key: str) -> None:
        key = self._get_key(idempotency_key)
        await self.redis.delete(key)
