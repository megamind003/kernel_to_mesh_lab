from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


class LocationModel(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    @field_validator('latitude', 'longitude')
    @classmethod
    def validate_precision(cls, v: float) -> float:
        return round(v, 6)


class TransactionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    idempotency_key: str = Field(..., min_length=16, max_length=64)
    user_id: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    merchant_id: str = Field(..., min_length=1, max_length=100)
    merchant_category: Optional[str] = Field(None, max_length=50)
    location: LocationModel
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('currency')
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        if v > Decimal('999999999999.99'):
            raise ValueError("Amount exceeds maximum allowed")
        return v


class TransactionResponse(BaseModel):
    transaction_id: int
    status: str
    fraud_score: Optional[float] = None
    ml_score: Optional[float] = None
    processing_time_ms: int
    blocked_reasons: Optional[list[str]] = None
    timestamp: datetime


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    database_healthy: bool
    redis_healthy: bool
    ml_model_loaded: bool
    avg_latency_ms: float
