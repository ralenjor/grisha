# KARKAS - Theater-Level Military Simulation Platform
# Multi-stage Dockerfile for C++ core + Python API

# =============================================================================
# Stage 1: Build C++ core library and Python bindings
# =============================================================================
FROM python:3.11-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    pkg-config \
    libgdal-dev \
    libpq-dev \
    libpython3-dev \
    pybind11-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy C++ source code
COPY CMakeLists.txt ./
COPY server/core/ ./server/core/
COPY tests/ ./tests/

# Build C++ core library
RUN mkdir -p build && cd build && \
    cmake .. \
        -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DKARKAS_BUILD_TESTS=OFF \
        -DKARKAS_BUILD_PYTHON_BINDINGS=ON && \
    ninja

# =============================================================================
# Stage 2: Runtime image
# =============================================================================
FROM python:3.11-slim-bookworm AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal32 \
    libpq5 \
    libproj25 \
    libgeos-c1v5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 karkas

# Set working directory
WORKDIR /app

# Copy Python package files first (for better layer caching)
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir pip setuptools wheel && \
    pip install --no-cache-dir \
        fastapi>=0.109.0 \
        uvicorn[standard]>=0.27.0 \
        websockets>=12.0 \
        pydantic>=2.5.0 \
        sqlalchemy>=2.0.0 \
        psycopg2-binary>=2.9.0 \
        geoalchemy2>=0.14.0 \
        shapely>=2.0.0 \
        numpy>=1.26.0 \
        pyyaml>=6.0 \
        httpx>=0.26.0 \
        asyncpg>=0.29.0

# Copy built C++ library from builder stage
COPY --from=builder /build/build/karkas_engine*.so /app/

# Copy Python application code
COPY server/ ./server/
COPY client/ ./client/
COPY tools/ ./tools/
COPY data/ ./data/

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default environment variables
ENV KARKAS_PORT=8080
ENV KARKAS_DB_ENABLED=true
ENV KARKAS_DB_HOST=db
ENV KARKAS_DB_PORT=5432
ENV KARKAS_DB_NAME=karkas
ENV KARKAS_DB_USER=karkas
ENV KARKAS_DB_PASSWORD=karkas

# Expose port
EXPOSE 8080

# Switch to non-root user
USER karkas

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"

# Entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command
CMD ["uvicorn", "server.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
