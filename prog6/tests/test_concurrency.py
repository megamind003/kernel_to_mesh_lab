import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.concurrency.idempotency import IdempotencyManager
from src.concurrency.locking import DeadlockDetector


@pytest.mark.asyncio
async def test_idempotency_manager():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    
    manager = IdempotencyManager(mock_redis)
    
    key = "test_key_123"
    response_data = {"transaction_id": 1, "status": "approved"}
    
    await manager.store_response(key, response_data)
    
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_idempotency_retrieval():
    import orjson
    
    mock_redis = AsyncMock()
    test_data = {"transaction_id": 42, "status": "blocked"}
    mock_redis.get = AsyncMock(return_value=orjson.dumps(test_data))
    
    manager = IdempotencyManager(mock_redis)
    
    result = await manager.get_response("some_key")
    
    assert result is not None
    assert result["transaction_id"] == 42
    assert result["status"] == "blocked"


def test_deadlock_detection():
    detector = DeadlockDetector()
    
    detector.add_wait_edge(1, 2)
    detector.add_wait_edge(2, 3)
    
    assert detector.has_deadlock() is False
    
    detector.add_wait_edge(3, 1)
    
    assert detector.has_deadlock() is True


def test_deadlock_removal():
    detector = DeadlockDetector()
    
    detector.add_wait_edge(1, 2)
    detector.add_wait_edge(2, 3)
    detector.add_wait_edge(3, 1)
    
    assert detector.has_deadlock() is True
    
    detector.remove_wait_edge(3, 1)
    
    assert detector.has_deadlock() is False


@pytest.mark.asyncio
async def test_concurrent_idempotency():
    mock_redis = AsyncMock()
    stored_data = {}
    
    async def mock_get(key):
        return stored_data.get(key)
    
    async def mock_setex(key, ttl, value):
        stored_data[key] = value
    
    mock_redis.get = mock_get
    mock_redis.setex = mock_setex
    
    manager = IdempotencyManager(mock_redis)
    
    key = "concurrent_key"
    data1 = {"transaction_id": 100, "status": "approved"}
    data2 = {"transaction_id": 200, "status": "blocked"}
    
    await asyncio.gather(
        manager.store_response(key, data1),
        manager.store_response(key, data2)
    )
    
    result = await manager.get_response(key)
    
    assert result is not None
    assert result["transaction_id"] in [100, 200]
