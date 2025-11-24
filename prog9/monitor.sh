#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Monitoring Chronos Performance"
echo "=============================="
echo ""

while true; do
    clear
    echo "Job Status Distribution:"
    echo "------------------------"
    sudo -u postgres psql -d chronos -t -c "SELECT status, COUNT(*) as count FROM jobs GROUP BY status ORDER BY status;"
    
    echo ""
    echo "Timing Wheel Status:"
    echo "-------------------"
    echo "Jobs in memory: $(grep -oP 'TimingWheel size: \K\d+' logs/chronos.log 2>/dev/null | tail -1 || echo 'N/A')"
    
    echo ""
    echo "Recent Activity (last 10 lines):"
    echo "--------------------------------"
    tail -n 10 logs/chronos.log 2>/dev/null || echo "No logs yet"
    
    echo ""
    echo "Database Connections:"
    echo "--------------------"
    sudo -u postgres psql -d chronos -t -c "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = 'chronos';"
    
    sleep 2
done
