#!/bin/bash
# Usage: ./run_node.sh <id> <port> [join_addr]

ID=$1
PORT=$2
JOIN=$3

if [ -z "$ID" ] || [ -z "$PORT" ]; then
    echo "Usage: ./run_node.sh <id> <port> [join_addr]"
    exit 1
fi

# Ensure libhydra is built
if [ ! -f "libhydra/target/release/libhydra_engine.so" ]; then
    echo "Building Rust library..."
    cd libhydra && cargo build --release && cd ..
fi

# Build Go binary if not exists
if [ ! -f "hydra" ]; then
    echo "Building Go binary..."
    export CGO_LDFLAGS="-L$(pwd)/libhydra/target/release -lhydra_engine"
    export LD_LIBRARY_PATH="$(pwd)/libhydra/target/release:$LD_LIBRARY_PATH"
    go build -o hydra ./cmd/hydra
fi

# Setup environment
export LD_LIBRARY_PATH="$(pwd)/libhydra/target/release:$LD_LIBRARY_PATH"
DATA_DIR="./tmp/hydra_${ID}"

mkdir -p $DATA_DIR

CMD="./hydra --id $ID --addr 127.0.0.1:$PORT --data-dir $DATA_DIR"

if [ ! -z "$JOIN" ]; then
    CMD="$CMD --join $JOIN"
fi

echo "Starting $ID on port $PORT..."
exec $CMD
