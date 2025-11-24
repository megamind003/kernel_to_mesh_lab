import asyncpg
from typing import Dict, Any
from datetime import datetime, timedelta
import time


class HistoricalContext:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.cache: Dict[int, Dict[str, Any]] = {}
        self.cache_ttl = 60
        self.cache_timestamps: Dict[int, float] = {}

    async def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        current_time = time.time()
        
        if user_id in self.cache:
            if current_time - self.cache_timestamps.get(user_id, 0) < self.cache_ttl:
                return self.cache[user_id]
        
        async with self.db_pool.acquire() as conn:
            user_data = await conn.fetchrow(
                "SELECT risk_score FROM users WHERE user_id = $1",
                user_id
            )
            
            if not user_data:
                await conn.execute(
                    "INSERT INTO users (user_id, risk_score) VALUES ($1, 0) ON CONFLICT DO NOTHING",
                    user_id
                )
                stats = {
                    "risk_score": 0,
                    "avg_amount": 0,
                    "txn_per_hour": 0
                }
            else:
                recent_stats = await conn.fetchrow(
                    """
                    WITH recent_velocity AS (
                        SELECT COALESCE(MAX(txn_per_hour), 0) as txn_per_hour
                        FROM hourly_velocity
                        WHERE user_id = $1 
                          AND bucket > NOW() - INTERVAL '1 hour'
                        LIMIT 1
                    ),
                    recent_spending AS (
                        SELECT COALESCE(AVG(avg_amount), 0) as avg_amount
                        FROM user_spending_stats_30d
                        WHERE user_id = $1 
                          AND bucket > NOW() - INTERVAL '7 days'
                        LIMIT 10
                    )
                    SELECT 
                        rv.txn_per_hour,
                        rs.avg_amount
                    FROM recent_velocity rv, recent_spending rs
                    """,
                    user_id
                )
                
                stats = {
                    "risk_score": user_data["risk_score"],
                    "avg_amount": float(recent_stats["avg_amount"] if recent_stats else 0),
                    "txn_per_hour": int(recent_stats["txn_per_hour"] if recent_stats else 0)
                }
            
            self.cache[user_id] = stats
            self.cache_timestamps[user_id] = current_time
            
            return stats

    async def update_user_risk_score(self, user_id: int, new_score: int) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET risk_score = $1, updated_at = NOW() WHERE user_id = $2",
                new_score,
                user_id
            )
        
        if user_id in self.cache:
            del self.cache[user_id]
