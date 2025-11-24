from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import random
import string
import time
from datetime import datetime


class TransactionUser(HttpUser):
    wait_time = between(0.001, 0.01)
    
    def on_start(self):
        self.user_ids = list(range(1, 10001))
        self.merchants = [f"merchant_{i:05d}" for i in range(1, 1001)]
        self.categories = ["retail", "food", "travel", "entertainment", "utilities"]
        self.locations = [
            (45.4642, 9.1900),
            (48.8566, 2.3522),
            (51.5074, -0.1278),
            (40.7128, -74.0060),
            (35.6762, 139.6503),
            (37.7749, -122.4194),
            (52.5200, 13.4050),
            (41.9028, 12.4964),
            (55.7558, 37.6173),
            (34.0522, -118.2437),
        ]
    
    def _generate_idempotency_key(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    
    def _generate_transaction(self):
        user_id = random.choice(self.user_ids)
        merchant_id = random.choice(self.merchants)
        category = random.choice(self.categories)
        location = random.choice(self.locations)
        
        is_fraud = random.random() < 0.05
        
        if is_fraud:
            amount = random.uniform(5000, 50000)
            location = random.choice(self.locations)
        else:
            amount = random.lognormvariate(4.5, 1.2)
        
        return {
            "idempotency_key": self._generate_idempotency_key(),
            "user_id": user_id,
            "amount": round(amount, 2),
            "currency": "EUR",
            "merchant_id": merchant_id,
            "merchant_category": category,
            "location": {
                "latitude": location[0],
                "longitude": location[1]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @task(10)
    def process_transaction(self):
        transaction = self._generate_transaction()
        
        with self.client.post(
            "/api/v1/transaction",
            json=transaction,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                
                if data.get("processing_time_ms", 1000) > 200:
                    response.failure(f"Latency too high: {data['processing_time_ms']}ms")
                else:
                    response.success()
            elif response.status_code == 503:
                response.failure("Service unavailable - backpressure")
            elif response.status_code == 429:
                response.failure("Rate limit exceeded")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def health_check(self):
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure("Health check failed")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    if isinstance(environment.runner, MasterRunner):
        print("Starting PANOPTICON stress test")
        print(f"Target: {environment.host}")
        print("Objective: 5000 TPS with P99 latency < 200ms")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\nStress test completed")
    
    stats = environment.stats
    
    if stats.total.num_requests > 0:
        print(f"\nTotal requests: {stats.total.num_requests}")
        print(f"Total failures: {stats.total.num_failures}")
        print(f"Failure rate: {stats.total.fail_ratio * 100:.2f}%")
        print(f"RPS: {stats.total.current_rps:.2f}")
        print(f"Average latency: {stats.total.avg_response_time:.2f}ms")
        print(f"P50 latency: {stats.total.get_response_time_percentile(0.5):.2f}ms")
        print(f"P95 latency: {stats.total.get_response_time_percentile(0.95):.2f}ms")
        print(f"P99 latency: {stats.total.get_response_time_percentile(0.99):.2f}ms")
        
        p99_latency = stats.total.get_response_time_percentile(0.99)
        
        if p99_latency > 200:
            print(f"\nWARNING: P99 latency {p99_latency:.2f}ms exceeds 200ms target")
        else:
            print(f"\nSUCCESS: P99 latency {p99_latency:.2f}ms meets 200ms target")
