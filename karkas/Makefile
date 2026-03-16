# KARKAS Makefile
# Common commands for development and deployment

.PHONY: help build run stop logs clean test dev shell db-shell lint format

# Default target
help:
	@echo "KARKAS - Theater-Level Military Simulation Platform"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make build      - Build Docker images"
	@echo "  make run        - Start all services (server + database)"
	@echo "  make stop       - Stop all services"
	@echo "  make logs       - Show server logs"
	@echo "  make clean      - Stop services and remove volumes"
	@echo "  make shell      - Open shell in server container"
	@echo "  make db-shell   - Open psql shell in database container"
	@echo ""
	@echo "Development Commands:"
	@echo "  make dev        - Start services with hot reload"
	@echo "  make test       - Run tests in container"
	@echo "  make lint       - Run linting tools"
	@echo "  make format     - Format code"
	@echo ""
	@echo "Local Commands:"
	@echo "  make build-cpp  - Build C++ core locally"
	@echo "  make run-local  - Run server locally (without Docker)"
	@echo "  make test-local - Run tests locally"

# =============================================================================
# Docker Commands
# =============================================================================

# Build Docker images
build:
	docker compose build

# Start all services
run:
	docker compose up -d
	@echo ""
	@echo "KARKAS is starting..."
	@echo "  Server: http://localhost:$${KARKAS_PORT:-8080}"
	@echo "  API Docs: http://localhost:$${KARKAS_PORT:-8080}/docs"
	@echo "  Database: localhost:$${KARKAS_DB_EXTERNAL_PORT:-5433}"
	@echo ""
	@echo "Use 'make logs' to view server logs"

# Stop all services
stop:
	docker compose down

# Show logs
logs:
	docker compose logs -f server

# Show all logs
logs-all:
	docker compose logs -f

# Clean up everything including volumes
clean:
	docker compose down -v
	docker rmi karkas-server 2>/dev/null || true

# Open shell in server container
shell:
	docker compose exec server /bin/bash

# Open psql shell in database
db-shell:
	docker compose exec db psql -U karkas -d karkas

# =============================================================================
# Development Commands
# =============================================================================

# Start with hot reload (mounts source code)
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Run tests in container
test:
	docker compose exec server pytest tests/ -v

# Run linting
lint:
	docker compose exec server python -m ruff check server/ client/ tools/

# Format code
format:
	docker compose exec server python -m black server/ client/ tools/

# =============================================================================
# Local Development Commands
# =============================================================================

# Build C++ core locally
build-cpp:
	mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release && make -j$$(nproc)

# Run server locally
run-local:
	./run_server.sh

# Run tests locally
test-local:
	pytest tests/ -v

# Run C++ tests locally
test-cpp:
	cd build && ctest --output-on-failure

# =============================================================================
# Database Commands
# =============================================================================

# Initialize database schema
db-init:
	docker compose exec server python -c "from server.database import init_database; init_database(create_tables=True)"

# Reset database (drops all data!)
db-reset:
	docker compose exec db psql -U karkas -d karkas -c "DROP SCHEMA IF EXISTS karkas CASCADE;"
	docker compose exec server python -c "from server.database import init_database; init_database(create_tables=True)"

# Backup database
db-backup:
	docker compose exec db pg_dump -U karkas karkas > backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup created: backup_$$(date +%Y%m%d_%H%M%S).sql"

# =============================================================================
# Utility Commands
# =============================================================================

# Check service health
health:
	@curl -s http://localhost:$${KARKAS_PORT:-8080}/health | python -m json.tool

# Show service status
status:
	docker compose ps

# Pull latest images
pull:
	docker compose pull

# Rebuild without cache
rebuild:
	docker compose build --no-cache
