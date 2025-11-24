#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p logs

echo "Starting Chronos Node..."
java -jar target/chronos-1.0.0.jar src/main/resources/chronos.properties
