import redis.asyncio as aioredis
from typing import Optional
from datetime import timedelta


class RedisStore:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def add_unique_merchant(self, user_id: int, merchant_id: str) -> int:
        key = f"user:{user_id}:merchants"
        
        script = """
        local key = KEYS[1]
        local merchant = ARGV[1]
        local ttl = ARGV[2]
        
        redis.call('PFADD', key, merchant)
        redis.call('EXPIRE', key, ttl)
        
        return redis.call('PFCOUNT', key)
        """
        
        count = await self.redis.eval(
            script,
            1,
            key,
            merchant_id,
            86400
        )
        
        return int(count)

    async def increment_transaction_counter(
        self,
        user_id: int,
        window_seconds: int = 3600
    ) -> int:
        key = f"user:{user_id}:txn_count"
        
        script = """
        local key = KEYS[1]
        local ttl = tonumber(ARGV[1])
        
        local current = redis.call('INCR', key)
        
        if current == 1 then
            redis.call('EXPIRE', key, ttl)
        end
        
        return current
        """
        
        count = await self.redis.eval(
            script,
            1,
            key,
            window_seconds
        )
        
        return int(count)

    async def set_with_ttl(
        self,
        key: str,
        value: str,
        ttl_seconds: int = 300
    ) -> None:
        await self.redis.setex(key, ttl_seconds, value)

    async def get(self, key: str) -> Optional[str]:
        return await self.redis.get(key)

    async def acquire_lock(
        self,
        lock_name: str,
        timeout_seconds: int = 10
    ) -> bool:
        lock_key = f"lock:{lock_name}"
        
        script = """
        local key = KEYS[1]
        local ttl = tonumber(ARGV[1])
        
        if redis.call('EXISTS', key) == 0 then
            redis.call('SETEX', key, ttl, '1')
            return 1
        else
            return 0
        end
        """
        
        acquired = await self.redis.eval(
            script,
            1,
            lock_key,
            timeout_seconds
        )
        
        return bool(acquired)

    async def release_lock(self, lock_name: str) -> None:
        lock_key = f"lock:{lock_name}"
        await self.redis.delete(lock_key)
