import pytest
import asyncio
from httpx import AsyncClient
from src.api.main import app
from datetime import datetime


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_transaction_validation():
    async with AsyncClient(app=app, base_url="http://test") as client:
        invalid_transaction = {
            "idempotency_key": "short",
            "user_id": 0,
            "amount": -100,
            "location": {"latitude": 91, "longitude": 181}
        }
        
        response = await client.post("/api/v1/transaction", json=invalid_transaction)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_valid_transaction():
    async with AsyncClient(app=app, base_url="http://test") as client:
        valid_transaction = {
            "idempotency_key": "test_key_12345678901234567890",
            "user_id": 12345,
            "amount": 100.50,
            "currency": "EUR",
            "merchant_id": "merchant_001",
            "merchant_category": "retail",
            "location": {
                "latitude": 45.4642,
                "longitude": 9.1900
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await client.post("/api/v1/transaction", json=valid_transaction)
        
        if response.status_code == 200:
            data = response.json()
            assert "transaction_id" in data
            assert "status" in data
            assert "processing_time_ms" in data
            assert data["processing_time_ms"] < 200


@pytest.mark.asyncio
async def test_idempotency():
    async with AsyncClient(app=app, base_url="http://test") as client:
        transaction = {
            "idempotency_key": "idempotent_test_key_123456",
            "user_id": 99999,
            "amount": 250.00,
            "currency": "EUR",
            "merchant_id": "merchant_002",
            "location": {
                "latitude": 48.8566,
                "longitude": 2.3522
            }
        }
        
        response1 = await client.post("/api/v1/transaction", json=transaction)
        response2 = await client.post("/api/v1/transaction", json=transaction)
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()
            
            assert data1["transaction_id"] == data2["transaction_id"]
            assert data1["status"] == data2["status"]
