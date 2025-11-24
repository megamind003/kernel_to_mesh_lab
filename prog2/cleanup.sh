#!/bin/bash
echo "Killing all hydra processes..."
pkill -9 hydra || echo "No hydra processes found."

echo "Cleaning up data directories..."
rm -rf ./tmp/hydra_*

echo "Done."
