import asyncpg
import redis.asyncio as aioredis
import asyncio
import time
from typing import Optional
from contextlib import asynccontextmanager


class PostgresLockManager:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    @asynccontextmanager
    async def advisory_lock(self, lock_id: int, nowait: bool = True):
        conn = await self.db_pool.acquire()
        
        try:
            if nowait:
                acquired = await conn.fetchval(
                    "SELECT pg_try_advisory_lock($1)",
                    lock_id
                )
                
                if not acquired:
                    raise asyncpg.exceptions.LockNotAvailableError("Could not acquire lock")
            else:
                await conn.execute("SELECT pg_advisory_lock($1)", lock_id)
            
            yield conn
        
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)
            await self.db_pool.release(conn)

    @asynccontextmanager
    async def row_lock_for_update(
        self,
        table: str,
        where_clause: str,
        params: tuple,
        nowait: bool = True
    ):
        conn = await self.db_pool.acquire()
        
        try:
            async with conn.transaction():
                nowait_clause = "NOWAIT" if nowait else ""
                
                query = f"""
                SELECT * FROM {table}
                WHERE {where_clause}
                FOR UPDATE {nowait_clause}
                """
                
                try:
                    row = await conn.fetchrow(query, *params)
                    yield conn, row
                except asyncpg.exceptions.LockNotAvailableError:
                    raise
        
        finally:
            await self.db_pool.release(conn)


class RedlockManager:
    def __init__(self, redis_clients: list[aioredis.Redis]):
        self.redis_clients = redis_clients
        self.quorum = len(redis_clients) // 2 + 1

    async def acquire_lock(
        self,
        lock_name: str,
        timeout_ms: int = 10000,
        retry_count: int = 3,
        retry_delay_ms: int = 200
    ) -> Optional[str]:
        lock_value = f"{time.time()}_{id(self)}"
        
        for attempt in range(retry_count):
            acquired_count = 0
            start_time = time.perf_counter()
            
            acquire_tasks = [
                self._acquire_single_lock(client, lock_name, lock_value, timeout_ms)
                for client in self.redis_clients
            ]
            
            results = await asyncio.gather(*acquire_tasks, return_exceptions=True)
            
            for result in results:
                if result is True:
                    acquired_count += 1
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            validity_time_ms = timeout_ms - elapsed_ms - 100
            
            if acquired_count >= self.quorum and validity_time_ms > 0:
                return lock_value
            
            await self.release_lock(lock_name, lock_value)
            
            if attempt < retry_count - 1:
                await asyncio.sleep(retry_delay_ms / 1000.0)
        
        return None

    async def _acquire_single_lock(
        self,
        redis_client: aioredis.Redis,
        lock_name: str,
        lock_value: str,
        timeout_ms: int
    ) -> bool:
        try:
            result = await redis_client.set(
                f"redlock:{lock_name}",
                lock_value,
                px=timeout_ms,
                nx=True
            )
            return result is True
        except Exception:
            return False

    async def release_lock(self, lock_name: str, lock_value: str) -> None:
        script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        
        release_tasks = [
            client.eval(script, 1, f"redlock:{lock_name}", lock_value)
            for client in self.redis_clients
        ]
        
        await asyncio.gather(*release_tasks, return_exceptions=True)


class DeadlockDetector:
    def __init__(self):
        self.lock_wait_graph: dict[int, set[int]] = {}

    def add_wait_edge(self, waiter_id: int, holder_id: int) -> None:
        if waiter_id not in self.lock_wait_graph:
            self.lock_wait_graph[waiter_id] = set()
        
        self.lock_wait_graph[waiter_id].add(holder_id)

    def remove_wait_edge(self, waiter_id: int, holder_id: int) -> None:
        if waiter_id in self.lock_wait_graph:
            self.lock_wait_graph[waiter_id].discard(holder_id)

    def detect_cycle(self, start_node: int, visited: set[int], rec_stack: set[int]) -> bool:
        visited.add(start_node)
        rec_stack.add(start_node)
        
        if start_node in self.lock_wait_graph:
            for neighbor in self.lock_wait_graph[start_node]:
                if neighbor not in visited:
                    if self.detect_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
        
        rec_stack.remove(start_node)
        return False

    def has_deadlock(self) -> bool:
        visited: set[int] = set()
        rec_stack: set[int] = set()
        
        for node in self.lock_wait_graph:
            if node not in visited:
                if self.detect_cycle(node, visited, rec_stack):
                    return True
        
        return False
