#!/bin/bash

# Exit on error
set -e

# Change to the app directory
cd /opt/render/project/src

# Run database migrations (if needed)
# alembic upgrade head

# Start the FastAPI application with Gunicorn
exec gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --timeout 120 \
    --keep-alive 10 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
