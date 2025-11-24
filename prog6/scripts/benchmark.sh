#!/bin/bash

set -e

echo "PANOPTICON Benchmark Script"
echo "============================"
echo ""

export DATABASE_URL=${DATABASE_URL:-"postgresql://panopticon:panopticon@localhost/panopticon"}
export REDIS_URL=${REDIS_URL:-"redis://localhost:6379/0"}

echo "Step 1: Initialize database"
python scripts/init_db.py

echo ""
echo "Step 2: Train ML model"
python src/ml/train.py

echo ""
echo "Step 3: Start API server in background"
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4 &
API_PID=$!

echo "Waiting for API to start..."
sleep 5

echo ""
echo "Step 4: Run quick health check"
curl -s http://localhost:8000/health | python -m json.tool

echo ""
echo "Step 5: Run unit tests"
pytest tests/ -v --cov=src --cov-report=term-missing

echo ""
echo "Step 6: Run stress test (1 minute, 1000 users)"
locust -f stress_test/locustfile.py \
    --headless \
    --users 1000 \
    --spawn-rate 50 \
    --run-time 60s \
    --host http://localhost:8000 \
    --html stress_test/report.html \
    --csv stress_test/results

echo ""
echo "Step 7: Analyze results"
python stress_test/analyze.py stress_test/results_stats.json

echo ""
echo "Stopping API server..."
kill $API_PID

echo ""
echo "Benchmark complete!"
