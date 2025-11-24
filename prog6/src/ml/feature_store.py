import redis.asyncio as aioredis
from typing import Dict, Any, Optional
import orjson
import time


class FeatureStore:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.ttl_seconds = 300

    def _get_key(self, user_id: int) -> str:
        return f"features:{user_id}"

    async def get_features(self, user_id: int) -> Optional[Dict[str, Any]]:
        key = self._get_key(user_id)
        
        data = await self.redis.get(key)
        
        if data:
            features = orjson.loads(data)
            return features
        
        return None

    async def store_features(
        self,
        user_id: int,
        features: Dict[str, Any]
    ) -> None:
        key = self._get_key(user_id)
        
        features["computed_at"] = time.time()
        
        serialized = orjson.dumps(features)
        
        await self.redis.setex(key, self.ttl_seconds, serialized)

    async def update_feature(
        self,
        user_id: int,
        feature_name: str,
        feature_value: Any
    ) -> None:
        features = await self.get_features(user_id)
        
        if features is None:
            features = {}
        
        features[feature_name] = feature_value
        
        await self.store_features(user_id, features)

    async def delete_features(self, user_id: int) -> None:
        key = self._get_key(user_id)
        await self.redis.delete(key)

    async def is_fresh(self, user_id: int, max_age_seconds: int = 300) -> bool:
        features = await self.get_features(user_id)
        
        if features is None:
            return False
        
        computed_at = features.get("computed_at", 0)
        age = time.time() - computed_at
        
        return age < max_age_seconds

    async def get_or_compute(
        self,
        user_id: int,
        compute_function,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        if not force_refresh:
            cached_features = await self.get_features(user_id)
            
            if cached_features is not None:
                if await self.is_fresh(user_id):
                    return cached_features
        
        fresh_features = await compute_function(user_id)
        
        await self.store_features(user_id, fresh_features)
        
        return fresh_features
