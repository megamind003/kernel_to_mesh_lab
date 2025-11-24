import asyncpg
import time
from typing import Dict, Any
from src.rules.parser import SafeExpressionParser


class RuleEvaluator:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.parser = SafeExpressionParser()
        self.rule_cache: Dict[int, Dict[str, Any]] = {}
        self.cache_timestamp = 0
        self.cache_ttl = 300

    async def load_rules(self) -> list[Dict[str, Any]]:
        current_time = time.time()
        
        if current_time - self.cache_timestamp < self.cache_ttl and self.rule_cache:
            return list(self.rule_cache.values())
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    rule_id,
                    rule_name,
                    rule_expression,
                    priority,
                    enabled,
                    shadow_mode
                FROM fraud_rules
                WHERE enabled = true
                ORDER BY priority DESC
                """
            )
        
        self.rule_cache = {
            row["rule_id"]: {
                "rule_id": row["rule_id"],
                "rule_name": row["rule_name"],
                "rule_expression": row["rule_expression"],
                "priority": row["priority"],
                "enabled": row["enabled"],
                "shadow_mode": row["shadow_mode"]
            }
            for row in rows
        }
        
        self.cache_timestamp = current_time
        
        return list(self.rule_cache.values())

    async def evaluate_rule(
        self,
        rule_expression: str,
        context: Dict[str, Any]
    ) -> bool:
        try:
            result = self.parser.safe_eval(rule_expression, context)
            return bool(result)
        except Exception:
            return False

    async def evaluate_all(self, context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        rules = await self.load_rules()
        
        results = {}
        
        for rule in rules:
            start_time = time.perf_counter()
            
            matched = await self.evaluate_rule(rule["rule_expression"], context)
            
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            results[rule["rule_name"]] = {
                "rule_id": rule["rule_id"],
                "matched": matched,
                "shadow_mode": rule["shadow_mode"],
                "priority": rule["priority"],
                "execution_time_ms": execution_time_ms
            }
        
        return results

    async def add_rule(
        self,
        rule_name: str,
        rule_expression: str,
        priority: int = 100,
        enabled: bool = True,
        shadow_mode: bool = False
    ) -> int:
        test_context = {
            "amount": 1000.0,
            "user_risk_score": 50,
            "avg_amount": 500.0,
            "transactions_per_hour": 5,
            "travel_speed": 0.0,
            "merchant_new": False,
            "hour": 12
        }
        
        try:
            self.parser.safe_eval(rule_expression, test_context)
        except Exception as e:
            raise ValueError(f"Invalid rule expression: {e}")
        
        async with self.db_pool.acquire() as conn:
            rule_id = await conn.fetchval(
                """
                INSERT INTO fraud_rules 
                (rule_name, rule_expression, priority, enabled, shadow_mode)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING rule_id
                """,
                rule_name,
                rule_expression,
                priority,
                enabled,
                shadow_mode
            )
        
        self.cache_timestamp = 0
        
        return rule_id

    async def update_rule_status(
        self,
        rule_id: int,
        enabled: bool | None = None,
        shadow_mode: bool | None = None
    ) -> None:
        updates = []
        values = []
        param_count = 1
        
        if enabled is not None:
            updates.append(f"enabled = ${param_count}")
            values.append(enabled)
            param_count += 1
        
        if shadow_mode is not None:
            updates.append(f"shadow_mode = ${param_count}")
            values.append(shadow_mode)
            param_count += 1
        
        if not updates:
            return
        
        values.append(rule_id)
        
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE fraud_rules 
                SET {', '.join(updates)}, updated_at = NOW()
                WHERE rule_id = ${param_count}
                """,
                *values
            )
        
        self.cache_timestamp = 0
