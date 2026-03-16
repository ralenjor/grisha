#!/bin/bash
# KARKAS Server Launch Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required"
    exit 1
fi

# Check for virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

# Install dependencies if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip install -e .
fi

# Set PYTHONPATH
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

# Default port
PORT=${KARKAS_PORT:-8080}

echo "Starting KARKAS Server on port $PORT..."
echo "API docs available at http://localhost:$PORT/docs"
echo ""

# Run server
python3 -m uvicorn server.api.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --reload
