#!/bin/bash
# KARKAS Docker Entrypoint Script
# Handles database initialization and server startup

set -e

echo "============================================"
echo "  KARKAS - Theater-Level Military Simulation"
echo "  Version: 0.1.0"
echo "============================================"

# Wait for database to be ready (if enabled)
if [ "$KARKAS_DB_ENABLED" = "true" ]; then
    echo "Waiting for database..."

    MAX_RETRIES=30
    RETRY_COUNT=0

    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if python -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='$KARKAS_DB_HOST',
        port=$KARKAS_DB_PORT,
        dbname='$KARKAS_DB_NAME',
        user='$KARKAS_DB_USER',
        password='$KARKAS_DB_PASSWORD'
    )
    conn.close()
    print('Database connection successful')
    exit(0)
except Exception as e:
    print(f'Waiting for database: {e}')
    exit(1)
" 2>/dev/null; then
            echo "Database is ready!"
            break
        fi

        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "Retry $RETRY_COUNT/$MAX_RETRIES..."
        sleep 2
    done

    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "Warning: Could not connect to database after $MAX_RETRIES attempts"
        echo "Starting server without database persistence..."
        export KARKAS_DB_ENABLED=false
    fi
fi

# Initialize database schema if enabled
if [ "$KARKAS_DB_ENABLED" = "true" ]; then
    echo "Initializing database schema..."
    python -c "
from server.database import init_database
try:
    init_database(create_tables=True)
    print('Database schema initialized successfully')
except Exception as e:
    print(f'Database initialization warning: {e}')
" 2>&1 || echo "Database initialization skipped"
fi

# Print configuration
echo ""
echo "Configuration:"
echo "  Port: $KARKAS_PORT"
echo "  Database: $KARKAS_DB_ENABLED"
if [ "$KARKAS_DB_ENABLED" = "true" ]; then
    echo "  DB Host: $KARKAS_DB_HOST:$KARKAS_DB_PORT"
    echo "  DB Name: $KARKAS_DB_NAME"
fi
if [ -n "$GRISHA_API_URL" ]; then
    echo "  Grisha API: $GRISHA_API_URL"
fi
if [ -n "$OLLAMA_HOST" ]; then
    echo "  Ollama: $OLLAMA_HOST"
fi
echo ""

# Execute the main command
echo "Starting KARKAS server..."
exec "$@"
