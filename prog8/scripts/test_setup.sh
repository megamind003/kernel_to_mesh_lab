#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Setting up AETHER test environment...${NC}"

# Build release if not exists
if [ ! -f "./target/release/aether" ]; then
    echo "Building AETHER..."
    cargo build --release
fi

# Create test directories
rm -rf test_env
mkdir -p test_env/peer1/storage
mkdir -p test_env/peer2/storage
mkdir -p test_env/data

# Link test data
echo "Linking test data..."
ln -sf /home/boss/Documents/prog/data_hardcore/alpine-minirootfs-3.22.2-x86_64.tar.gz test_env/data/small_file.tar.gz
ln -sf /home/boss/Documents/prog/data_hardcore/tearsofsteel_4k.mov test_env/data/large_file.mov

echo -e "${GREEN}Test environment ready.${NC}"
