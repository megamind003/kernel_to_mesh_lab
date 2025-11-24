import asyncpg
from datetime import datetime
from typing import Optional
import time


class SpatialContext:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.location_cache: dict[int, tuple] = {}
        self.cache_timestamps: dict[int, float] = {}
        self.cache_ttl = 30

    async def check_impossible_travel(
        self,
        user_id: int,
        current_lat: float,
        current_lon: float,
        current_time: datetime
    ) -> float:
        current_ts = time.time()
        
        if user_id in self.location_cache:
            cache_age = current_ts - self.cache_timestamps.get(user_id, 0)
            if cache_age < self.cache_ttl:
                last_location, last_timestamp = self.location_cache[user_id]
                
                time_diff_seconds = (current_time - last_timestamp).total_seconds()
                
                if time_diff_seconds <= 0 or not last_location:
                    return 0.0
                
                async with self.db_pool.acquire() as conn:
                    speed_kmh = await conn.fetchval(
                        """
                        SELECT calculate_travel_speed(
                            $1::geography,
                            ST_SetSRID(ST_MakePoint($2, $3), 4326)::geography,
                            $4
                        )
                        """,
                        last_location,
                        current_lon,
                        current_lat,
                        int(time_diff_seconds)
                    )
                    
                    return float(speed_kmh or 0.0)
        
        async with self.db_pool.acquire() as conn:
            last_transaction = await conn.fetchrow(
                """
                SELECT location, timestamp
                FROM transactions
                WHERE user_id = $1 AND timestamp < $2
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                user_id,
                current_time
            )
            
            if not last_transaction or not last_transaction["location"]:
                return 0.0
            
            self.location_cache[user_id] = (
                last_transaction["location"],
                last_transaction["timestamp"]
            )
            self.cache_timestamps[user_id] = current_ts
            
            time_diff_seconds = (current_time - last_transaction["timestamp"]).total_seconds()
            
            if time_diff_seconds <= 0:
                return 0.0
            
            speed_kmh = await conn.fetchval(
                """
                SELECT calculate_travel_speed(
                    $1::geography,
                    ST_SetSRID(ST_MakePoint($2, $3), 4326)::geography,
                    $4
                )
                """,
                last_transaction["location"],
                current_lon,
                current_lat,
                int(time_diff_seconds)
            )
            
            return float(speed_kmh or 0.0)
