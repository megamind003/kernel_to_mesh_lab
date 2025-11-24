from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import ORJSONResponse
from contextlib import asynccontextmanager
import asyncpg
import redis.asyncio as aioredis
from datetime import datetime
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response as FastAPIResponse
import asyncio

from src.api.schemas import TransactionRequest, TransactionResponse, HealthResponse
from src.api.middleware import RequestIDMiddleware, PerformanceMiddleware
from src.context.historical import HistoricalContext
from src.context.spatial import SpatialContext
from src.context.redis_store import RedisStore
from src.rules.evaluator import RuleEvaluator
from src.concurrency.idempotency import IdempotencyManager
from src.ml.inference import MLInference
import os


TRANSACTION_COUNTER = Counter('transactions_total', 'Total transactions processed', ['status'])
LATENCY_HISTOGRAM = Histogram('transaction_latency_seconds', 'Transaction processing latency')
FRAUD_SCORE_HISTOGRAM = Histogram('fraud_score', 'Distribution of fraud scores')


class AppState:
    def __init__(self) -> None:
        self.db_pool: asyncpg.Pool | None = None
        self.redis_client: aioredis.Redis | None = None
        self.historical_context: HistoricalContext | None = None
        self.spatial_context: SpatialContext | None = None
        self.redis_store: RedisStore | None = None
        self.rule_evaluator: RuleEvaluator | None = None
        self.idempotency_manager: IdempotencyManager | None = None
        self.ml_inference: MLInference | None = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.getenv("DATABASE_URL", "postgresql://panopticon:panopticon@localhost/panopticon")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    app_state.db_pool = await asyncpg.create_pool(
        database_url,
        min_size=int(os.getenv("DATABASE_POOL_MIN_SIZE", "20")),
        max_size=int(os.getenv("DATABASE_POOL_MAX_SIZE", "100")),
        command_timeout=float(os.getenv("DB_STATEMENT_TIMEOUT_MS", "50")) / 1000.0
    )
    
    app_state.redis_client = await aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=int(os.getenv("REDIS_POOL_SIZE", "50"))
    )
    
    app_state.historical_context = HistoricalContext(app_state.db_pool)
    app_state.spatial_context = SpatialContext(app_state.db_pool)
    app_state.redis_store = RedisStore(app_state.redis_client)
    app_state.rule_evaluator = RuleEvaluator(app_state.db_pool)
    app_state.idempotency_manager = IdempotencyManager(app_state.redis_client)
    
    ml_model_path = os.getenv("ML_MODEL_PATH", "./models/fraud_detector.onnx")
    app_state.ml_inference = MLInference(ml_model_path)
    await app_state.ml_inference.load_model()
    
    yield
    
    if app_state.db_pool:
        await app_state.db_pool.close()
    if app_state.redis_client:
        await app_state.redis_client.close()


app = FastAPI(
    title="PANOPTICON",
    description="High-Frequency Financial Sentinel",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(PerformanceMiddleware)


@app.post("/api/v1/transaction", response_model=TransactionResponse)
async def process_transaction(request: Request, transaction: TransactionRequest) -> TransactionResponse:
    start_time = time.perf_counter()
    
    cached_response = await app_state.idempotency_manager.get_response(
        transaction.idempotency_key
    )
    if cached_response:
        return TransactionResponse(**cached_response)
    
    try:
        async with app_state.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock($1)",
                    hash(transaction.user_id) % (2**31)
                )
                
                user_stats_task = app_state.historical_context.get_user_statistics(
                    transaction.user_id
                )
                
                travel_speed_task = app_state.spatial_context.check_impossible_travel(
                    transaction.user_id,
                    transaction.location.latitude,
                    transaction.location.longitude,
                    transaction.timestamp
                )
                
                merchant_count_task = app_state.redis_store.add_unique_merchant(
                    transaction.user_id,
                    transaction.merchant_id
                )
                
                user_stats, travel_speed, merchant_count = await asyncio.gather(
                    user_stats_task,
                    travel_speed_task,
                    merchant_count_task
                )
                
                context = {
                    "amount": float(transaction.amount),
                    "user_risk_score": user_stats.get("risk_score", 0),
                    "avg_amount": user_stats.get("avg_amount", 0),
                    "transactions_per_hour": user_stats.get("txn_per_hour", 0),
                    "travel_speed": travel_speed,
                    "merchant_new": merchant_count == 1,
                    "hour": transaction.timestamp.hour,
                }
                
                rule_task = app_state.rule_evaluator.evaluate_all(context)
                ml_task = app_state.ml_inference.predict_from_context(context)
                
                rule_results, ml_score = await asyncio.gather(rule_task, ml_task)
                
                fraud_score = max(
                    sum(1 for r in rule_results.values() if r.get("matched")) / len(rule_results) if rule_results else 0,
                    ml_score
                )
                
                status = "blocked" if fraud_score > 0.6 else "approved"
                blocked_reasons = [
                    name for name, result in rule_results.items() 
                    if result.get("matched") and not result.get("shadow_mode")
                ] if status == "blocked" else None
                
                txn_id = await conn.fetchval(
                    """
                    INSERT INTO transactions 
                    (idempotency_key, user_id, amount, currency, merchant_id, 
                     merchant_category, location, timestamp, status, fraud_score, 
                     ml_score, rule_results, processing_time_ms)
                    VALUES ($1, $2, $3, $4, $5, $6, ST_SetSRID(ST_MakePoint($7, $8), 4326)::geography,
                            $9, $10, $11, $12, $13, $14)
                    RETURNING transaction_id
                    """,
                    transaction.idempotency_key,
                    transaction.user_id,
                    transaction.amount,
                    transaction.currency,
                    transaction.merchant_id,
                    transaction.merchant_category,
                    transaction.location.longitude,
                    transaction.location.latitude,
                    transaction.timestamp,
                    status,
                    fraud_score,
                    ml_score,
                    rule_results,
                    int((time.perf_counter() - start_time) * 1000)
                )
        
        processing_time_ms = int((time.perf_counter() - start_time) * 1000)
        
        response_data = {
            "transaction_id": txn_id,
            "status": status,
            "fraud_score": fraud_score,
            "ml_score": ml_score,
            "processing_time_ms": processing_time_ms,
            "blocked_reasons": blocked_reasons,
            "timestamp": transaction.timestamp
        }
        
        await app_state.idempotency_manager.store_response(
            transaction.idempotency_key,
            response_data
        )
        
        TRANSACTION_COUNTER.labels(status=status).inc()
        LATENCY_HISTOGRAM.observe(processing_time_ms / 1000.0)
        FRAUD_SCORE_HISTOGRAM.observe(fraud_score)
        
        return TransactionResponse(**response_data)
        
    except asyncpg.exceptions.UniqueViolationError:
        cached = await app_state.idempotency_manager.get_response(transaction.idempotency_key)
        if cached:
            return TransactionResponse(**cached)
        raise HTTPException(status_code=409, detail="Duplicate transaction")
    except asyncpg.exceptions.LockNotAvailableError:
        raise HTTPException(status_code=503, detail="Resource temporarily unavailable")
    except Exception as e:
        TRANSACTION_COUNTER.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    db_healthy = False
    redis_healthy = False
    ml_loaded = app_state.ml_inference.model_loaded if app_state.ml_inference else False
    
    try:
        async with app_state.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_healthy = True
    except Exception:
        pass
    
    try:
        await app_state.redis_client.ping()
        redis_healthy = True
    except Exception:
        pass
    
    return HealthResponse(
        status="healthy" if (db_healthy and redis_healthy and ml_loaded) else "degraded",
        timestamp=datetime.utcnow(),
        database_healthy=db_healthy,
        redis_healthy=redis_healthy,
        ml_model_loaded=ml_loaded,
        avg_latency_ms=50.0
    )


@app.get("/metrics")
async def metrics() -> FastAPIResponse:
    return FastAPIResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
