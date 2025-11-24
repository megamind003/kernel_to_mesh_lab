#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Setting up PostgreSQL database..."

sudo -u postgres psql -c "DROP DATABASE IF EXISTS chronos;" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE chronos;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE chronos TO postgres;"

echo "Database 'chronos' created successfully"

echo "Initializing schema..."
sudo -u postgres psql -d chronos -f schema.sql

echo "Setup complete"
