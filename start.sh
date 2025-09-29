#!/bin/bash

set -euo pipefail

# Check if we're running inside Docker by checking if we're the 'app' user
if [ "$(whoami)" = "app" ]; then
    # Running inside Docker - virtual environment is already activated via Dockerfile
    echo "Running inside Docker container with user: $(whoami)"
else
    # Activate virtual environment if it exists (for local development)
    if [ -f .venv/bin/activate ]; then
        source .venv/bin/activate
        echo "Activated virtual environment for local development"
    fi
fi

# Default to running the FastAPI server unless overridden
: "${HOST:=0.0.0.0}"
: "${PORT:=8000}"

exec uvicorn app.main:app --host "$HOST" --port "$PORT"
