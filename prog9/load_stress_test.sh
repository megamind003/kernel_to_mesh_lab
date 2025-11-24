#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CSV_PATH="../data_hardcore/creditcard.csv"

if [ ! -f "$CSV_PATH" ]; then
    echo "Error: creditcard.csv not found at $CSV_PATH"
    exit 1
fi

echo "Building project..."
mvn clean package -DskipTests

echo ""
echo "Loading stress test data from creditcard.csv..."
echo "This will create 284,807 jobs with time-based delays"
echo ""

java -cp target/chronos-1.0.0.jar com.chronos.StressTestLoader "$CSV_PATH"

echo ""
echo "Checking job distribution..."
sudo -u postgres psql -d chronos -c "SELECT status, COUNT(*) FROM jobs GROUP BY status;"

echo ""
echo "Sample of scheduled jobs:"
sudo -u postgres psql -d chronos -c "SELECT id, scheduled_at, job_type, tenant_id FROM jobs ORDER BY scheduled_at LIMIT 10;"

echo ""
echo "Stress test data loaded successfully"
