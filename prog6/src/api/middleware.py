from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import uuid
from typing import Callable
import asyncio


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response


class PerformanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        process_time_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time-MS"] = f"{process_time_ms:.2f}"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_requests: int = 5000, window_seconds: int = 1):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = {}
        self.lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_id = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        async with self.lock:
            if client_id not in self.requests:
                self.requests[client_id] = []
            
            self.requests[client_id] = [
                t for t in self.requests[client_id] 
                if current_time - t < self.window_seconds
            ]
            
            if len(self.requests[client_id]) >= self.max_requests:
                return Response(
                    content='{"error": "Rate limit exceeded"}',
                    status_code=429,
                    headers={"Content-Type": "application/json"}
                )
            
            self.requests[client_id].append(current_time)
        
        return await call_next(request)
